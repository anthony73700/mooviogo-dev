from unittest.mock import patch
from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.phone_verification import create_phone_otp, verify_phone_otp

User = get_user_model()


class AuthPhoneAndOAuthTests(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_verify_phone_otp_returns_verification_token(self):
        phone = "+33612345678"
        code = create_phone_otp(phone)

        response = self.client.post(
            "/api/v1/auth/phone/verify-otp/",
            {"phone": phone, "code": code},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone"], phone)
        self.assertTrue(response.data.get("phone_verification_token"))

    @override_settings(DEBUG=True)
    @patch("apps.authentication.views.send_notification_task")
    def test_request_phone_otp_returns_debug_code_in_debug(self, mock_task):
        phone = "+33623456789"
        mock_task.delay.return_value = None

        response = self.client.post(
            "/api/v1/auth/phone/request-otp/",
            {"phone": phone},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("debug_code", response.data)
        self.assertEqual(len(response.data["debug_code"]), 6)

    @patch.dict("apps.authentication.views.RequestPhoneOTPThrottle.THROTTLE_RATES", {"otp_request": "1/day"}, clear=False)
    def test_request_phone_otp_is_throttled(self):
        self.client.post(
            "/api/v1/auth/phone/request-otp/",
            {"phone": "+33623456789"},
            format="json",
        )
        response = self.client.post(
            "/api/v1/auth/phone/request-otp/",
            {"phone": "+33623456789"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch.dict("apps.authentication.views.VerifyPhoneOTPThrottle.THROTTLE_RATES", {"otp_verify": "1/day"}, clear=False)
    def test_verify_phone_otp_is_throttled(self):
        self.client.post(
            "/api/v1/auth/phone/verify-otp/",
            {"phone": "+33623456789", "code": "123456"},
            format="json",
        )
        response = self.client.post(
            "/api/v1/auth/phone/verify-otp/",
            {"phone": "+33623456789", "code": "123456"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_verify_phone_otp_progressive_backoff_after_invalid_attempts(self):
        phone = "+33677778888"

        first = self.client.post(
            "/api/v1/auth/phone/verify-otp/",
            {"phone": phone, "code": "111111"},
            format="json",
        )
        second = self.client.post(
            "/api/v1/auth/phone/verify-otp/",
            {"phone": phone, "code": "111111"},
            format="json",
        )
        third = self.client.post(
            "/api/v1/auth/phone/verify-otp/",
            {"phone": phone, "code": "111111"},
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(third.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("blocked_seconds", third.data)

    def test_register_requires_valid_phone_token(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "newuser@example.com",
                "username": "newuser",
                "display_name": "New User",
                "birth_date": "1996-03-12",
                "phone": "+33698765432",
                "phone_verification_token": "bad-token",
                "password": "strong-pass-123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_with_valid_phone_token_creates_user(self):
        phone = "+33611111111"
        code = create_phone_otp(phone)
        token = verify_phone_otp(phone, code)

        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "otpuser@example.com",
                "username": "otpuser",
                "display_name": "OTP User",
                "birth_date": "1992-07-01",
                "phone": phone,
                "phone_verification_token": token,
                "password": "strong-pass-123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="otpuser@example.com")
        self.assertEqual(user.phone, phone)
        self.assertIsNotNone(user.phone_verified_at)

    @patch("apps.authentication.views.get_social_profile")
    def test_social_login_creates_user_when_missing(self, mock_get_social_profile):
        mock_get_social_profile.return_value = {
            "external_id": "google-sub-1",
            "email": "social.new@example.com",
            "display_name": "Social New",
        }

        phone = "+33622222222"
        code = create_phone_otp(phone)
        token = verify_phone_otp(phone, code)

        response = self.client.post(
            "/api/v1/auth/social-login/",
            {
                "provider": "google",
                "access_token": "token",
                "birth_date": "1990-05-08",
                "phone": phone,
                "phone_verification_token": token,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["created"])
        self.assertTrue(response.data["tokens"]["access"])
        self.assertTrue(response.data["tokens"]["refresh"])

    @patch("apps.authentication.views.get_social_profile")
    def test_social_login_existing_user_returns_tokens(self, mock_get_social_profile):
        user = User.objects.create_user(
            username="socialexisting",
            email="social.existing@example.com",
            password="strong-pass-123",
            birth_date=date(1991, 2, 1),
        )

        mock_get_social_profile.return_value = {
            "external_id": "google-sub-existing",
            "email": user.email,
            "display_name": "Social Existing",
        }

        response = self.client.post(
            "/api/v1/auth/social-login/",
            {
                "provider": "google",
                "access_token": "token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["created"])
        self.assertEqual(response.data["user"]["email"], user.email)
        self.assertTrue(response.data["tokens"]["access"])
