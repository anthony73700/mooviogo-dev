from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.reports.models import Report

User = get_user_model()


class ReportModerationApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="strong-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        self.reporter = User.objects.create_user(
            username="reporter",
            email="reporter@example.com",
            password="strong-pass-123",
        )
        self.target_user = User.objects.create_user(
            username="target",
            email="target@example.com",
            password="strong-pass-123",
        )
        self.report = Report.objects.create(
            reporter=self.reporter,
            target_type=Report.TargetType.USER,
            target_id=self.target_user.id,
            category=Report.Category.HARASSMENT,
            reason="Harassment message",
        )

    def test_assign_sets_in_review_and_sla(self):
        self.client.force_authenticate(self.admin)
        with patch("apps.reports.views.send_report_moderation_notifications") as mock_notify:
            response = self.client.post(
                f"/api/v1/reports/{self.report.id}/assign/",
                {"sla_hours": 12},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.IN_REVIEW)
        self.assertEqual(self.report.assigned_moderator_id, self.admin.id)
        self.assertIsNotNone(self.report.sla_due_at)
        mock_notify.assert_called_once()

    def test_moderate_ban_user_disables_target_and_sets_resolution_code(self):
        self.client.force_authenticate(self.admin)
        with patch("apps.reports.views.send_report_moderation_notifications") as mock_notify:
            response = self.client.post(
                f"/api/v1/reports/{self.report.id}/moderate/",
                {"action": "ban_user", "notes": "Severe abuse"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.report.refresh_from_db()
        self.target_user.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.RESOLVED)
        self.assertEqual(self.report.resolution_code, Report.ResolutionCode.USER_BANNED)
        self.assertFalse(self.target_user.is_active)
        mock_notify.assert_called_once()
