from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

User = get_user_model()


class SignupPhoneOTPWebFlowTests(TestCase):
    @override_settings(DEBUG=True)
    @patch("apps.web.views.send_notification_task")
    def test_signup_request_otp_returns_debug_code(self, mock_task):
        mock_task.delay.return_value = None

        response = self.client.post("/inscription/request-otp/", {"phone": "+33612349876"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("debug_code", payload)
        self.assertEqual(len(payload["debug_code"]), 6)

    @patch("apps.web.views._is_rate_limited", return_value=True)
    @patch("apps.web.views.send_notification_task")
    def test_signup_request_otp_is_rate_limited(self, mock_task, _mock_rate_limited):
        response = self.client.post("/inscription/request-otp/", {"phone": "+33612349876"})

        self.assertEqual(response.status_code, 429)
        self.assertIn("detail", response.json())
        self.assertFalse(mock_task.delay.called)

    @patch("apps.web.views.get_phone_otp_block_remaining", return_value=120)
    @patch("apps.web.views.send_notification_task")
    def test_signup_request_otp_is_blocked_for_phone_backoff(self, mock_task, _mock_blocked):
        response = self.client.post("/inscription/request-otp/", {"phone": "+33612349876"})

        self.assertEqual(response.status_code, 429)
        payload = response.json()
        self.assertEqual(payload.get("blocked_seconds"), 120)
        self.assertFalse(mock_task.delay.called)

    def test_signup_rejects_without_otp_code(self):
        response = self.client.post(
            "/inscription/",
            {
                "username": "user-no-otp",
                "email": "user-no-otp@example.com",
                "phone": "+33600000001",
                "birth_date": "1990-01-01",
                "password": "strong-pass-123",
                "password2": "strong-pass-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Le code OTP est obligatoire")
        self.assertFalse(User.objects.filter(email="user-no-otp@example.com").exists())

    @override_settings(DEBUG=True)
    @patch("apps.web.views.send_notification_task")
    def test_signup_creates_user_with_valid_otp(self, mock_task):
        mock_task.delay.return_value = None

        otp_response = self.client.post("/inscription/request-otp/", {"phone": "+33611119999"})
        self.assertEqual(otp_response.status_code, 200)
        otp_code = otp_response.json()["debug_code"]

        response = self.client.post(
            "/inscription/",
            {
                "username": "otp-web-user",
                "email": "otp-web-user@example.com",
                "phone": "+33611119999",
                "otp_code": otp_code,
                "birth_date": "1994-06-15",
                "password": "strong-pass-123",
                "password2": "strong-pass-123",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="otp-web-user@example.com")
        self.assertEqual(user.phone, "+33611119999")
        self.assertIsNotNone(user.phone_verified_at)
