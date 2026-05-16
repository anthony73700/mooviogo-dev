import json

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from mooviogo.observability import emit_alert, emit_event

from .models import WebPushSubscription


def _send_twilio_message(channel, to, message):
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        return {"provider": "twilio", "status": "skipped", "reason": "credentials_not_configured"}

    from twilio.rest import Client

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    if channel == "sms":
        from_number = settings.TWILIO_FROM_SMS
        if not from_number:
            return {"provider": "twilio", "status": "skipped", "reason": "from_sms_not_configured"}
        msg = client.messages.create(from_=from_number, to=to, body=message)
        return {"provider": "twilio", "status": "sent", "sid": msg.sid}

    if channel == "whatsapp":
        from_whatsapp = settings.TWILIO_FROM_WHATSAPP
        if not from_whatsapp:
            return {"provider": "twilio", "status": "skipped", "reason": "from_whatsapp_not_configured"}
        to_whatsapp = to if str(to).startswith("whatsapp:") else f"whatsapp:{to}"
        msg = client.messages.create(from_=from_whatsapp, to=to_whatsapp, body=message)
        return {"provider": "twilio", "status": "sent", "sid": msg.sid}

    return {"provider": "twilio", "status": "skipped", "reason": "unsupported_channel"}


def _resolve_push_target_user(to):
    to_str = str(to or "").strip()
    if not to_str:
        return None

    if to_str.isdigit():
        return int(to_str)

    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(email__iexact=to_str).only("id").first()
    return user.id if user else None


def _send_web_push(to, message, subject):
    if not settings.WEB_PUSH_VAPID_PRIVATE_KEY or not settings.WEB_PUSH_VAPID_CLAIMS_SUBJECT:
        return {"provider": "webpush", "status": "skipped", "reason": "vapid_not_configured"}

    target_user_id = _resolve_push_target_user(to)
    if not target_user_id:
        return {"provider": "webpush", "status": "skipped", "reason": "target_user_not_found"}

    subscriptions = list(
        WebPushSubscription.objects.filter(user_id=target_user_id, is_active=True).order_by("-updated_at")
    )
    if not subscriptions:
        return {"provider": "webpush", "status": "skipped", "reason": "no_active_subscriptions"}

    from pywebpush import WebPushException, webpush

    payload = json.dumps(
        {
            "title": subject or "Mooviogo",
            "body": message,
            "to": str(to),
        }
    )

    success_count = 0
    for sub in subscriptions:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth,
            },
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=settings.WEB_PUSH_VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.WEB_PUSH_VAPID_CLAIMS_SUBJECT},
            )
            sub.last_success_at = timezone.now()
            sub.last_error = ""
            sub.save(update_fields=["last_success_at", "last_error", "updated_at"])
            success_count += 1
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            # 404/410 means the subscription is stale on browser side.
            if status_code in {404, 410}:
                sub.is_active = False
            sub.last_error = str(exc)[:250]
            sub.save(update_fields=["is_active", "last_error", "updated_at"])

    if success_count == 0:
        return {
            "provider": "webpush",
            "status": "failed",
            "reason": "all_deliveries_failed",
            "subscriptions": len(subscriptions),
        }

    return {
        "provider": "webpush",
        "status": "sent",
        "delivered": success_count,
        "subscriptions": len(subscriptions),
    }


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_notification_task(self, channel, to, message, subject="Mooviogo Notification"):
    channel = (channel or "").lower().strip()

    if channel == "email":
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            fail_silently=False,
        )
        emit_event("notifications.email.sent", channel=channel, to=to)
        return {"status": "sent", "channel": channel, "to": to}

    if channel in {"sms", "whatsapp"}:
        result = _send_twilio_message(channel=channel, to=to, message=message)
        emit_event(
            "notifications.twilio.sent",
            channel=channel,
            to=to,
            sid=result.get("sid", ""),
            provider_status=result.get("status", "unknown"),
            reason=result.get("reason", ""),
        )
        response_status = "sent" if result.get("status") == "sent" else "accepted"
        return {"status": response_status, "channel": channel, "to": to, **result}

    if channel == "push":
        result = _send_web_push(to=to, message=message, subject=subject)
        emit_event(
            "notifications.webpush.sent",
            channel=channel,
            to=to,
            delivered=result.get("delivered", 0),
            provider_status=result.get("status", "unknown"),
            reason=result.get("reason", ""),
        )
        response_status = "sent" if result.get("status") == "sent" else "accepted"
        return {"status": response_status, "channel": channel, "to": to, **result}

    emit_alert("notifications.channel.invalid", severity="warning", channel=channel, to=to)
    return {"status": "ignored", "channel": channel, "to": to}
