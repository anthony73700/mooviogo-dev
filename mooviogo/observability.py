import json
import logging

from django.core.cache import cache
from django.utils import timezone


_event_logger = logging.getLogger("mooviogo.observability.event")
_alert_logger = logging.getLogger("mooviogo.observability.alert")


def _request_context(request):
    if request is None:
        return {
            "user_id": None,
            "ip": "unknown",
            "path": "",
            "method": "",
        }
    user = getattr(request, "user", None)
    return {
        "user_id": getattr(user, "id", None) if user and getattr(user, "is_authenticated", False) else None,
        "ip": request.META.get("REMOTE_ADDR", "unknown"),
        "path": request.path,
        "method": request.method,
    }


def emit_event(event_name, request=None, **fields):
    payload = {
        "kind": "event",
        "event": event_name,
        "at": timezone.now().isoformat(),
    }
    payload.update(_request_context(request))
    payload.update(fields)
    _event_logger.info(json.dumps(payload, ensure_ascii=True, default=str))


def emit_alert(alert_name, request=None, severity="warning", **fields):
    payload = {
        "kind": "alert",
        "alert": alert_name,
        "severity": severity,
        "at": timezone.now().isoformat(),
    }
    payload.update(_request_context(request))
    payload.update(fields)
    line = json.dumps(payload, ensure_ascii=True, default=str)
    if severity in ("error", "critical"):
        _alert_logger.error(line)
    else:
        _alert_logger.warning(line)


def increment_window_counter(counter_key, window_seconds):
    if cache.add(counter_key, 1, timeout=window_seconds):
        return 1
    try:
        return cache.incr(counter_key)
    except ValueError:
        cache.set(counter_key, 1, timeout=window_seconds)
        return 1


def alert_on_threshold(counter_key, *, threshold, window_seconds, alert_name, request=None, severity="warning", **fields):
    current = increment_window_counter(counter_key, window_seconds)
    if current == threshold:
        emit_alert(
            alert_name,
            request=request,
            severity=severity,
            threshold=threshold,
            window_seconds=window_seconds,
            current=current,
            **fields,
        )
    return current
