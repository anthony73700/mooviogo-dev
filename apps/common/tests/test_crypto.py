"""Tests for the symmetric encryption helper."""

import pytest
from django.test import override_settings

from apps.common.crypto import decrypt_text, encrypt_text


def test_round_trip_with_secret_key_fallback():
    token = encrypt_text("0612345678")
    assert token != "0612345678"
    assert decrypt_text(token) == "0612345678"


def test_empty_input_returns_empty():
    assert encrypt_text("") == ""
    assert decrypt_text("") == ""


def test_tampered_token_raises():
    token = encrypt_text("secret")
    with pytest.raises(ValueError):
        decrypt_text(token[:-2] + "xx")


@override_settings(DATA_ENCRYPTION_KEY="custom-passphrase-for-prod-keep-safe")
def test_custom_passphrase_round_trip():
    token = encrypt_text("private")
    assert decrypt_text(token) == "private"


def test_different_calls_produce_different_ciphertext():
    """Fernet embeds a timestamp + IV, so ciphertexts differ each call."""
    a = encrypt_text("same")
    b = encrypt_text("same")
    assert a != b
    assert decrypt_text(a) == decrypt_text(b) == "same"
