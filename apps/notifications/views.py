import uuid

from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from mooviogo.observability import emit_alert, emit_event

from .models import WebPushSubscription
from .tasks import send_notification_task


class NotificationSendThrottle(UserRateThrottle):
    scope = "notification_send"


class NotificationSendSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=["push", "email", "sms", "whatsapp"])
    subject = serializers.CharField(required=False, allow_blank=True, max_length=120)
    message = serializers.CharField(max_length=1000)
    to = serializers.CharField(max_length=255)

    def validate(self, attrs):
        if attrs["channel"] == "email":
            try:
                validate_email(attrs["to"])
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"to": "Adresse email invalide."}) from exc
        return attrs


class WebPushSubscriptionSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=500)
    keys = serializers.DictField()

    def validate(self, attrs):
        keys = attrs.get("keys") or {}
        p256dh = (keys.get("p256dh") or "").strip()
        auth_key = (keys.get("auth") or "").strip()
        if not p256dh or not auth_key:
            raise serializers.ValidationError({"keys": "Les champs keys.p256dh et keys.auth sont requis."})
        attrs["p256dh"] = p256dh
        attrs["auth"] = auth_key
        return attrs


class NotificationSendView(APIView):
    permission_classes = [permissions.IsAdminUser]
    throttle_classes = [NotificationSendThrottle]

    def post(self, request):
        serializer = NotificationSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            try:
                send_notification_task.delay(
                    channel=data["channel"],
                    to=data["to"],
                    message=data["message"],
                    subject=data.get("subject") or "Mooviogo Notification",
                )
            except Exception:
                # Fallback for local/dev/test environments without a running broker.
                send_notification_task.run(
                    channel=data["channel"],
                    to=data["to"],
                    message=data["message"],
                    subject=data.get("subject") or "Mooviogo Notification",
                )
            emit_event("notifications.queued", request=request, channel=data["channel"], to=data["to"])
        except Exception as exc:
            emit_alert(
                "notifications.send_failed",
                request=request,
                severity="error",
                channel=data.get("channel", "unknown"),
                to=data.get("to", ""),
                error=str(exc),
            )
            return Response(
                {"detail": "Echec mise en file de la notification."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "notification_id": str(uuid.uuid4()),
                "status": "queued",
                "channel": data["channel"],
            },
            status=status.HTTP_202_ACCEPTED,
        )


class WebPushPublicKeyView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not settings.WEB_PUSH_VAPID_PUBLIC_KEY:
            return Response(
                {"detail": "Web push public key is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"public_key": settings.WEB_PUSH_VAPID_PUBLIC_KEY}, status=status.HTTP_200_OK)


class WebPushSubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = WebPushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        sub, _ = WebPushSubscription.objects.update_or_create(
            endpoint=data["endpoint"],
            defaults={
                "user": request.user,
                "p256dh": data["p256dh"],
                "auth": data["auth"],
                "is_active": True,
                "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:255],
                "last_error": "",
            },
        )
        emit_event("notifications.webpush.subscription_upserted", request=request, subscription_id=sub.id)
        return Response({"subscription_id": sub.id, "status": "active"}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        endpoint = (request.data.get("endpoint") or "").strip()
        if not endpoint:
            return Response({"detail": "endpoint is required."}, status=status.HTTP_400_BAD_REQUEST)

        updated = WebPushSubscription.objects.filter(user=request.user, endpoint=endpoint).update(is_active=False)
        emit_event("notifications.webpush.subscription_disabled", request=request, disabled=updated)
        return Response({"disabled": updated}, status=status.HTTP_200_OK)
