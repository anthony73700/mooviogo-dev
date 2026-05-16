"""Application-level symmetric encryption helper.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the ``cryptography`` package,
which is already a hard dependency.

Key resolution order:
  1. ``DATA_ENCRYPTION_KEY`` env (recommended — rotatable independently)
  2. Derived deterministically from ``SECRET_KEY`` (dev fallback)

USAGE
-----
::

    from apps.common.crypto import encrypt_text, decrypt_text

    ciphertext = encrypt_text("0612345678")
    plaintext = decrypt_text(ciphertext)

WHEN TO USE
-----------
Apply to NEW columns that store sensitive data **and** are never used in
``filter(...)`` lookups or unique constraints (e.g. moderator notes, audit
payloads, encrypted backups of PII).

Do **not** retrofit it on ``User.phone`` / ``User.birth_date`` without first
introducing a deterministic hashed-lookup column — see ``docs/security.md``.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _derive_key() -> bytes:
    key = getattr(settings, "DATA_ENCRYPTION_KEY", "") or ""
    if key:
        # Allow either a raw Fernet key (urlsafe base64 of 32 bytes) or any
        # passphrase: hash to 32 bytes then urlsafe-b64 encode.
        try:
            Fernet(key.encode())
            return key.encode()
        except (ValueError, TypeError):
            pass
        digest = hashlib.sha256(key.encode()).digest()
        return base64.urlsafe_b64encode(digest)

    # Dev fallback — derived from SECRET_KEY so tests work without extra config.
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(_derive_key())


def encrypt_text(plaintext: str) -> str:
    """Encrypt a string and return a URL-safe base64 token."""
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_text(token: str) -> str:
    """Decrypt a token. Raises ``ValueError`` on tamper / wrong key."""
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Invalid or tampered ciphertext") from exc
