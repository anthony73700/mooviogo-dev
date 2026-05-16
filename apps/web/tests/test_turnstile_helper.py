"""Cloudflare Turnstile helper tests."""

from unittest.mock import patch

from django.test import override_settings

from apps.web.turnstile import verify_turnstile


@override_settings(TURNSTILE_SECRET_KEY="")
def test_turnstile_bypassed_when_secret_empty():
    assert verify_turnstile("") is True
    assert verify_turnstile("anything") is True


@override_settings(TURNSTILE_SECRET_KEY="dummy")
def test_turnstile_rejects_empty_token_when_enabled():
    assert verify_turnstile("") is False


@override_settings(TURNSTILE_SECRET_KEY="dummy")
def test_turnstile_accepts_valid_response():
    class _Resp:
        def json(self):
            return {"success": True}

    with patch("apps.web.turnstile.requests.post", return_value=_Resp()):
        assert verify_turnstile("token") is True


@override_settings(TURNSTILE_SECRET_KEY="dummy")
def test_turnstile_rejects_invalid_response():
    class _Resp:
        def json(self):
            return {"success": False, "error-codes": ["invalid-input-response"]}

    with patch("apps.web.turnstile.requests.post", return_value=_Resp()):
        assert verify_turnstile("token") is False
