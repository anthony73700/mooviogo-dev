"""Health endpoints.

`/api/health/` is a lightweight liveness probe (DB ping).
`/api/health/ready/` is a deeper readiness probe (DB + Redis + Celery).
"""

from django.conf import settings
from django.db import connection
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """Liveness probe — checks DB connection only."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        db_ok = True
        try:
            connection.ensure_connection()
        except Exception:
            db_ok = False

        payload = {
            "status": "ok" if db_ok else "degraded",
            "db": "ok" if db_ok else "error",
        }
        return Response(payload, status=200 if db_ok else 503)


class ReadinessCheckView(APIView):
    """Readiness probe — DB + Redis (cache) + Celery broker."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        checks = {}

        # DB
        try:
            connection.ensure_connection()
            checks["db"] = "ok"
        except Exception as exc:
            checks["db"] = f"error: {type(exc).__name__}"

        # Redis cache
        try:
            from django.core.cache import cache
            cache.set("_readiness_probe", "1", timeout=5)
            checks["cache"] = "ok" if cache.get("_readiness_probe") == "1" else "error"
        except Exception as exc:
            checks["cache"] = f"error: {type(exc).__name__}"

        # Celery broker ping (best-effort, short timeout)
        try:
            from celery import current_app
            insp = current_app.control.inspect(timeout=1)
            pong = insp.ping() or {}
            checks["celery"] = "ok" if pong else "no-workers"
        except Exception as exc:
            checks["celery"] = f"error: {type(exc).__name__}"

        ok = checks.get("db") == "ok" and checks.get("cache") == "ok"
        payload = {"status": "ok" if ok else "degraded", **checks}
        return Response(payload, status=200 if ok else 503)
