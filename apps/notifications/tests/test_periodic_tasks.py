"""Smoke tests for Celery Beat configuration."""

from django.conf import settings


def test_celery_beat_schedule_contains_expected_tasks():
    schedule = getattr(settings, "CELERY_BEAT_SCHEDULE", {})
    assert "expire-pending-tickets-every-30min" in schedule
    assert "send-event-reminders-hourly" in schedule
    assert "cleanup-expired-otp-keys-daily" in schedule
    for entry in schedule.values():
        assert entry["task"].startswith("apps.notifications.periodic.")
        assert entry["schedule"] is not None


def test_celery_periodic_tasks_are_importable():
    from apps.notifications import periodic

    assert callable(periodic.expire_stale_pending_tickets)
    assert callable(periodic.send_upcoming_event_reminders)
    assert callable(periodic.cleanup_expired_otp_keys)


def test_cleanup_otp_heartbeat_runs_without_error():
    from apps.notifications.periodic import cleanup_expired_otp_keys

    assert cleanup_expired_otp_keys() == {"ok": True}
