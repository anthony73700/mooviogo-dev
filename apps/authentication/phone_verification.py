import random
import re
import uuid
from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone


OTP_TTL_SECONDS = 10 * 60
VERIFIED_TOKEN_TTL_SECONDS = 30 * 60
OTP_FAIL_WINDOW_SECONDS = 12 * 60 * 60
OTP_BLOCK_BASE_SECONDS = 5 * 60
OTP_BLOCK_MAX_SECONDS = 6 * 60 * 60
OTP_BLOCK_TRIGGER_ATTEMPTS = 3
PHONE_REGEX = re.compile(r"^\+?[1-9]\d{7,14}$")


def normalize_phone(phone: str) -> str:
    return (phone or "").replace(" ", "").replace("-", "").strip()


def is_phone_format_valid(phone: str) -> bool:
    return bool(PHONE_REGEX.match(normalize_phone(phone)))


def _otp_cache_key(phone: str) -> str:
    return f"auth:phone:otp:{normalize_phone(phone)}"


def _verified_cache_key(phone: str) -> str:
    return f"auth:phone:verified:{normalize_phone(phone)}"


def _otp_fail_count_key(phone: str) -> str:
    return f"auth:phone:otp:fail-count:{normalize_phone(phone)}"


def _otp_blocked_until_key(phone: str) -> str:
    return f"auth:phone:otp:blocked-until:{normalize_phone(phone)}"


def _otp_alert_daily_key() -> str:
    return timezone.now().strftime("metrics:otp_alerts:%Y%m%d")


def increment_otp_alert_metric() -> int:
    key = _otp_alert_daily_key()
    if cache.add(key, 1, timeout=2 * 24 * 60 * 60):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=2 * 24 * 60 * 60)
        return 1


def get_otp_alerts_last_24h() -> int:
    now = timezone.now()
    today_key = now.strftime("metrics:otp_alerts:%Y%m%d")
    yesterday_key = (now - timedelta(days=1)).strftime("metrics:otp_alerts:%Y%m%d")
    return int(cache.get(today_key) or 0) + int(cache.get(yesterday_key) or 0)


def get_phone_otp_block_remaining(phone: str) -> int:
    normalized = normalize_phone(phone)
    blocked_until = cache.get(_otp_blocked_until_key(normalized))
    if not blocked_until:
        return 0
    now_ts = int(timezone.now().timestamp())
    remaining = int(blocked_until) - now_ts
    if remaining <= 0:
        cache.delete(_otp_blocked_until_key(normalized))
        return 0
    return remaining


def clear_phone_otp_backoff(phone: str) -> None:
    normalized = normalize_phone(phone)
    cache.delete(_otp_fail_count_key(normalized))
    cache.delete(_otp_blocked_until_key(normalized))


def register_phone_otp_failed_attempt(phone: str) -> int:
    normalized = normalize_phone(phone)
    fail_key = _otp_fail_count_key(normalized)
    if cache.add(fail_key, 1, timeout=OTP_FAIL_WINDOW_SECONDS):
        fail_count = 1
    else:
        try:
            fail_count = int(cache.incr(fail_key))
        except ValueError:
            cache.set(fail_key, 1, timeout=OTP_FAIL_WINDOW_SECONDS)
            fail_count = 1

    if fail_count < OTP_BLOCK_TRIGGER_ATTEMPTS:
        return 0

    exponent = fail_count - OTP_BLOCK_TRIGGER_ATTEMPTS
    block_seconds = min(OTP_BLOCK_BASE_SECONDS * (2 ** exponent), OTP_BLOCK_MAX_SECONDS)
    blocked_until = int(timezone.now().timestamp()) + block_seconds
    cache.set(_otp_blocked_until_key(normalized), blocked_until, timeout=block_seconds)
    increment_otp_alert_metric()
    return block_seconds


def create_phone_otp(phone: str) -> str:
    normalized = normalize_phone(phone)
    code = f"{random.randint(0, 999999):06d}"
    cache.set(
        _otp_cache_key(normalized),
        {
            "code": code,
            "created_at": timezone.now().isoformat(),
        },
        timeout=OTP_TTL_SECONDS,
    )
    return code


def verify_phone_otp(phone: str, code: str) -> str | None:
    normalized = normalize_phone(phone)
    if get_phone_otp_block_remaining(normalized) > 0:
        return None

    payload = cache.get(_otp_cache_key(normalized)) or {}
    expected = str(payload.get("code") or "")
    if not expected or str(code or "").strip() != expected:
        register_phone_otp_failed_attempt(normalized)
        return None

    token = uuid.uuid4().hex
    cache.set(
        _verified_cache_key(normalized),
        {
            "token": token,
            "verified_at": timezone.now().isoformat(),
        },
        timeout=VERIFIED_TOKEN_TTL_SECONDS,
    )
    cache.delete(_otp_cache_key(normalized))
    clear_phone_otp_backoff(normalized)
    return token


def is_phone_verification_token_valid(phone: str, token: str) -> bool:
    normalized = normalize_phone(phone)
    payload = cache.get(_verified_cache_key(normalized)) or {}
    return bool(payload.get("token") and payload.get("token") == str(token or "").strip())


def consume_phone_verification_token(phone: str, token: str) -> bool:
    normalized = normalize_phone(phone)
    if not is_phone_verification_token_valid(normalized, token):
        return False
    cache.delete(_verified_cache_key(normalized))
    return True


def get_phone_verified_at(phone: str) -> datetime:
    normalized = normalize_phone(phone)
    payload = cache.get(_verified_cache_key(normalized)) or {}
    verified_at_raw = payload.get("verified_at")
    if not verified_at_raw:
        return timezone.now()
    parsed = datetime.fromisoformat(verified_at_raw)
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed
