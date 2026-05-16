from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.authentication.social import SocialAuthError, get_apple_profile


class SocialSecurityTests(TestCase):
    @override_settings(APPLE_CLIENT_ID="com.mooviogo.web", APPLE_JWKS_URL="https://appleid.apple.com/auth/keys")
    @patch("apps.authentication.social.jwt.decode")
    @patch("apps.authentication.social.jwt.PyJWKClient")
    def test_apple_profile_verifies_signature_and_audience(self, mock_jwk_client, mock_decode):
        signing_key = MagicMock()
        signing_key.key = "public-key"
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = signing_key
        mock_decode.return_value = {
            "sub": "apple-user-1",
            "email": "apple@example.com",
        }

        profile = get_apple_profile("id-token")

        self.assertEqual(profile["external_id"], "apple-user-1")
        self.assertEqual(profile["email"], "apple@example.com")
        mock_decode.assert_called_once_with(
            "id-token",
            "public-key",
            algorithms=["RS256"],
            audience="com.mooviogo.web",
            issuer="https://appleid.apple.com",
        )

    @override_settings(APPLE_CLIENT_ID="")
    def test_apple_profile_requires_client_id_setting(self):
        with self.assertRaises(SocialAuthError):
            get_apple_profile("id-token")
