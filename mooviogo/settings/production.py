"""Production settings.

Reads sensitive values from environment. See .env.production.example.
"""

import os

import environ

from .base import *  # noqa: F401, F403
from .base import BASE_DIR, env  # explicit re-import

# ─── Hard sanity checks ───────────────────────────────────────────────────────
DEBUG = False

if not env("SECRET_KEY", default=""):
    raise RuntimeError("SECRET_KEY must be set in production")

# Allowed hosts / CSRF — bail loudly if not configured.
if not env.list("ALLOWED_HOSTS", default=[]):
    raise RuntimeError("ALLOWED_HOSTS must be set in production")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ─── HTTPS / cookies / headers ────────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 14 days

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # Django reads it client-side for AJAX
CSRF_COOKIE_SAMESITE = "Lax"

# ─── Database — persistent connections ────────────────────────────────────────
if "default" in DATABASES:  # noqa: F405  (DATABASES imported from base)
    DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)  # noqa: F405
    DATABASES["default"].setdefault("OPTIONS", {})  # noqa: F405
    # Force SSL when using Postgres in prod
    if DATABASES["default"].get("ENGINE", "").endswith("postgresql"):  # noqa: F405
        DATABASES["default"]["OPTIONS"].setdefault("sslmode", "require")  # noqa: F405

# ─── Cache (Redis) ────────────────────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/1"),
        "TIMEOUT": 300,
    }
}

# ─── Object storage (S3 / Cloudflare R2) for MEDIA ───────────────────────────
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
if AWS_STORAGE_BUCKET_NAME:
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="auto")
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
    AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default="")
    AWS_QUERYSTRING_AUTH = env.bool("AWS_QUERYSTRING_AUTH", default=False)
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"

# ─── Email — fail fast if console backend leaks into prod ─────────────────────
if EMAIL_BACKEND.endswith("console.EmailBackend"):  # noqa: F405
    # Allow opt-in via env (e.g. early staging), otherwise warn loudly.
    if not env.bool("ALLOW_CONSOLE_EMAIL", default=False):
        import warnings
        warnings.warn(
            "EMAIL_BACKEND is the console backend in production. "
            "Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend "
            "and configure EMAIL_HOST/EMAIL_HOST_USER/EMAIL_HOST_PASSWORD.",
            RuntimeWarning,
        )

EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

# ─── Sentry (optional — lazy init if DSN provided) ────────────────────────────
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.redis import RedisIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=env("SENTRY_ENVIRONMENT", default="production"),
            release=env("SENTRY_RELEASE", default=None),
            integrations=[
                DjangoIntegration(),
                CeleryIntegration(),
                RedisIntegration(),
            ],
            traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.05),
            profiles_sample_rate=env.float("SENTRY_PROFILES_SAMPLE_RATE", default=0.0),
            send_default_pii=False,
        )
    except ImportError:
        # sentry-sdk not installed — silently skip
        pass

# ─── Logging (JSON to stdout, picked up by container runtime) ────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": (
                '{"time":"%(asctime)s","level":"%(levelname)s",'
                '"name":"%(name)s","message":"%(message)s"}'
            ),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "mooviogo.observability.event": {
            "handlers": ["console"], "level": "INFO", "propagate": False,
        },
        "mooviogo.observability.alert": {
            "handlers": ["console"], "level": "WARNING", "propagate": False,
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
