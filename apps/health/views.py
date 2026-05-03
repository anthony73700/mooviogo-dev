from django.db import connection
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import permissions


class HealthCheckView(APIView):
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
        http_status = 200 if db_ok else 503
        return Response(payload, status=http_status)
