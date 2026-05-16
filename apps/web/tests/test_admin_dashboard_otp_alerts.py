from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase


User = get_user_model()


class AdminDashboardOtpAlertsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-otp-kpi",
            email="admin-otp-kpi@example.com",
            password="strong-pass-123",
            is_staff=True,
            is_superuser=True,
        )

    @patch("apps.web.views.get_otp_alerts_last_24h", return_value=7)
    def test_admin_dashboard_includes_otp_alerts_kpi(self, _mock_alerts):
        self.client.force_login(self.admin)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["kpis"]["otp_alerts_24h"], 7)
