"""Cloudflare Turnstile verification helper.

If ``TURNSTILE_SECRET_KEY`` is empty (dev / tests), verification is bypassed.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token: str, *, remote_ip: str = "") -> bool:
    """Return True if Turnstile is disabled or the token is valid."""
    secret = getattr(settings, "TURNSTILE_SECRET_KEY", "")
    if not secret:
        return True
    if not token:
        return False
    try:
        response = requests.post(
            _VERIFY_URL,
            data={"secret": secret, "response": token, "remoteip": remote_ip},
            timeout=5,
        )
        return bool(response.json().get("success"))
    except Exception as exc:  # noqa: BLE001 — fail closed only on missing token
        logger.warning("turnstile_verify_failed", extra={"error": str(exc)})
        return False
