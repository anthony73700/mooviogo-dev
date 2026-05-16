from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

User = get_user_model()


class PasswordResetWebFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reset-user",
            email="reset@example.com",
            password="old-pass-123",
        )

    @patch("apps.web.views.send_mail")
    def test_forgot_password_sends_email_for_existing_user(self, mock_send_mail):
        response = self.client.post("/forgot-password/", {"email": self.user.email}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_send_mail.called)

    @patch("apps.web.views.cache.get", return_value=999)
    @patch("apps.web.views.send_mail")
    @patch("apps.web.views.emit_alert")
    def test_forgot_password_is_rate_limited(self, mock_emit_alert, mock_send_mail, _mock_cache_get):
        response = self.client.post("/forgot-password/", {"email": self.user.email}, follow=False)

        self.assertEqual(response.status_code, 429)
        self.assertFalse(mock_send_mail.called)
        self.assertTrue(mock_emit_alert.called)

    def test_reset_password_confirm_updates_password(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.post(
            f"/reset-password/{uidb64}/{token}/",
            {
                "new_password1": "new-strong-pass-123",
                "new_password2": "new-strong-pass-123",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-strong-pass-123"))
