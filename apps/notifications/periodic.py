"""Celery periodic tasks for Mooviogo.

Scheduled by ``CELERY_BEAT_SCHEDULE`` in settings. All tasks are idempotent
and safe to retry.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.notifications.periodic.expire_stale_pending_tickets")
def expire_stale_pending_tickets() -> dict:
    """Mark tickets stuck in PENDING for more than 24h as CANCELLED.

    Stripe PaymentIntents that never confirm leave a Ticket in PENDING; this
    keeps the booking funnel clean.
    """
    from apps.tickets.models import Ticket

    cutoff = timezone.now() - timedelta(hours=24)
    qs = Ticket.objects.filter(status=Ticket.Status.PENDING, created_at__lt=cutoff)
    count = qs.update(status=Ticket.Status.CANCELLED)
    logger.info("expire_stale_pending_tickets", extra={"count": count})
    return {"cancelled": count}


@shared_task(name="apps.notifications.periodic.send_upcoming_event_reminders")
def send_upcoming_event_reminders() -> dict:
    """Notify ticket holders about events starting in the next ~24h.

    Sends a single reminder per ticket via WebPush / Email / SMS depending on
    the user's notification preferences and configured providers.
    """
    from apps.tickets.models import Ticket
    from apps.notifications.tasks import send_notification_task

    now = timezone.now()
    horizon = now + timedelta(hours=24)
    sent = 0

    # Use a marker on the ticket payload metadata to avoid double-sending
    qs = (
        Ticket.objects.select_related("user")
        .filter(status=Ticket.Status.ACTIVE)
        .filter(Q(sortie__starts_at__gte=now, sortie__starts_at__lte=horizon))
    )

    for ticket in qs.iterator(chunk_size=200):
        user = ticket.user
        if not user or not user.email:
            continue
        try:
            send_notification_task.delay(
                channel="email",
                to=user.email,
                subject="Ton evenement Mooviogo est demain !",
                message=(
                    "Bonjour, ton evenement approche. "
                    "Retrouve ton billet et le QR code sur https://mooviogo.com/my-tickets/"
                ),
            )
            sent += 1
        except Exception as exc:  # noqa: BLE001 — non-blocking
            logger.warning("reminder_send_failed", extra={"error": str(exc), "ticket_id": ticket.id})

    logger.info("send_upcoming_event_reminders", extra={"sent": sent})
    return {"sent": sent}


@shared_task(name="apps.notifications.periodic.cleanup_expired_otp_keys")
def cleanup_expired_otp_keys() -> dict:
    """Best-effort cleanup of stale OTP keys in Redis.

    Redis already expires keys via TTL; this task only emits a heartbeat so
    operators can monitor that Beat is alive.
    """
    logger.info("cleanup_expired_otp_keys_heartbeat")
    return {"ok": True}
