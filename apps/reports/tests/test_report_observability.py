from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.reports.models import Report

User = get_user_model()


class ReportObservabilityTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-obs",
            email="admin-obs@example.com",
            password="strong-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        self.target_user = User.objects.create_user(
            username="target-obs",
            email="target-obs@example.com",
            password="strong-pass-123",
        )
        self.report = Report.objects.create(
            target_type=Report.TargetType.USER,
            target_id=self.target_user.id,
            category=Report.Category.HARASSMENT,
            reason="Severe harassment",
        )

    @patch("apps.reports.views.emit_alert")
    @patch("apps.reports.views.emit_event")
    @patch("apps.reports.views.send_report_moderation_notifications")
    def test_ban_user_emits_alert_and_event(self, _mock_notify, mock_emit_event, mock_emit_alert):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            f"/api/v1/reports/{self.report.id}/moderate/",
            {"action": "ban_user", "notes": "Critical abuse"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(mock_emit_event.called)
        self.assertTrue(mock_emit_alert.called)
