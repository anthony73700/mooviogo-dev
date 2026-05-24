"""
Base settings for Mooviogo Django project.

All shared settings go here. Environment-specific files (development.py,
production.py) import from here and override as needed.
"""

from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / "subdir"
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)

# Read .env if present
environ.Env.read_env(BASE_DIR / ".env")

# ─── Security ──────────────────────────────────────────────────────────────────

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ─── Application definition ────────────────────────────────────────────────────

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "channels",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
]

LOCAL_APPS = [
    "apps.common",
    "apps.users",
    "apps.authentication",
    "apps.ai",
    "apps.ads",
    "apps.sorties",
    "apps.restaurants",
    "apps.bookings",
    "apps.chats",
    "apps.events",
    "apps.notifications",
    "apps.public_events",
    "apps.partners",
    "apps.partner_opportunities",
    "apps.payments",
    "apps.tickets",
    "apps.city_feed",
    "apps.reports",
    "apps.health",
    "apps.web",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware ─────────────────────────────────────────────────────────────────

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.web.middleware.UserPreferredLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mooviogo.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.web.context_processors.site_config",
            ],
        },
    },
]

WSGI_APPLICATION = "mooviogo.wsgi.application"
ASGI_APPLICATION = "mooviogo.asgi.application"

# ─── Database ──────────────────────────────────────────────────────────────────

DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3"),
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Custom user model ─────────────────────────────────────────────────────────

AUTH_USER_MODEL = "users.User"
LOGIN_URL = "/connexion/"
LOGIN_REDIRECT_URL = "/"

# ─── Password validation ───────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── Internationalisation ──────────────────────────────────────────────────────

LANGUAGE_CODE = "fr-fr"
LANGUAGES = [
    ("fr", "Francais"),
    ("en", "English"),
    ("es", "Espanol"),
]
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

# ─── Static / Media ────────────────────────────────────────────────────────────

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ─── Django REST Framework ─────────────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "otp_request": "8/hour",
        "otp_verify": "20/hour",
        "ticket_validate": "90/min",
        "ticket_scan_audits": "120/min",
        "report_moderation": "60/min",
        "notification_send": "20/min",
    },
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
}

# ─── JWT ───────────────────────────────────────────────────────────────────────

from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("ACCESS_TOKEN_LIFETIME_MINUTES", default=60)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("REFRESH_TOKEN_LIFETIME_DAYS", default=30)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
}

# ─── CORS ──────────────────────────────────────────────────────────────────────

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

# ─── Redis / Celery ────────────────────────────────────────────────────────────

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# ─── Email ─────────────────────────────────────────────────────────────────────

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@mooviogo.com")

# ─── Stripe ────────────────────────────────────────────────────────────────────

STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
APP_BASE_URL = env("APP_BASE_URL", default="http://localhost:8000")

# ─── OAuth Apple ─────────────────────────────────────────────────────────────

APPLE_CLIENT_ID = env("APPLE_CLIENT_ID", default="")
APPLE_TEAM_ID = env("APPLE_TEAM_ID", default="")
APPLE_KEY_ID = env("APPLE_KEY_ID", default="")
APPLE_JWKS_URL = env("APPLE_JWKS_URL", default="https://appleid.apple.com/auth/keys")

# ─── Analytics / tracking ─────────────────────────────────────────────────────

ENABLE_ANALYTICS = env.bool("ENABLE_ANALYTICS", default=False)
GA4_MEASUREMENT_ID = env("GA4_MEASUREMENT_ID", default="")
POSTHOG_KEY = env("POSTHOG_KEY", default="")
POSTHOG_HOST = env("POSTHOG_HOST", default="https://eu.i.posthog.com")
META_PIXEL_ID = env("META_PIXEL_ID", default="")
TIKTOK_PIXEL_ID = env("TIKTOK_PIXEL_ID", default="")

# ─── Twilio notifications ───────────────────────────────────────────────────────

TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", default="")
TWILIO_FROM_SMS = env("TWILIO_FROM_SMS", default="")
TWILIO_FROM_WHATSAPP = env("TWILIO_FROM_WHATSAPP", default="")

# ─── Web Push (VAPID) ──────────────────────────────────────────────────────────

WEB_PUSH_VAPID_PUBLIC_KEY = env("WEB_PUSH_VAPID_PUBLIC_KEY", default="")
WEB_PUSH_VAPID_PRIVATE_KEY = env("WEB_PUSH_VAPID_PRIVATE_KEY", default="")
WEB_PUSH_VAPID_CLAIMS_SUBJECT = env("WEB_PUSH_VAPID_CLAIMS_SUBJECT", default="mailto:hello@mooviogo.com")

# ─── Geocoding / maps ────────────────────────────────────────────────────────

GEOCODING_ENABLED = env.bool("GEOCODING_ENABLED", default=True)
GEOCODING_PROVIDER = env("GEOCODING_PROVIDER", default="nominatim")
GEOCODING_NOMINATIM_URL = env("GEOCODING_NOMINATIM_URL", default="https://nominatim.openstreetmap.org/search")
GEOCODING_USER_AGENT = env("GEOCODING_USER_AGENT", default="mooviogo/1.0 (hello@mooviogo.com)")

# ─── Google Maps (carte interactive) ─────────────────────────────────────────

GOOGLE_MAPS_API_KEY = env("GOOGLE_MAPS_API_KEY", default="")

# ─── OpenAI (recommandations, génération contenu, marketing) ────────────────

OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
OPENAI_MODEL = env("OPENAI_MODEL", default="gpt-4o-mini")
OPENAI_TIMEOUT_SECONDS = env.int("OPENAI_TIMEOUT_SECONDS", default=20)

# ─── Anti-bot (Cloudflare Turnstile) ─────────────────────────────────────────

TURNSTILE_SITE_KEY = env("TURNSTILE_SITE_KEY", default="")
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", default="")

# Application-level data encryption key (Fernet). Optional — falls back to a
# key derived from SECRET_KEY in dev. Generate via:
#     python manage.py generate_encryption_key
DATA_ENCRYPTION_KEY = env("DATA_ENCRYPTION_KEY", default="")

# ─── Celery Beat (tâches périodiques) ────────────────────────────────────────

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    "expire-pending-tickets-every-30min": {
        "task": "apps.notifications.periodic.expire_stale_pending_tickets",
        "schedule": crontab(minute="*/30"),
    },
    "send-event-reminders-hourly": {
        "task": "apps.notifications.periodic.send_upcoming_event_reminders",
        "schedule": crontab(minute=5),
    },
    "cleanup-expired-otp-keys-daily": {
        "task": "apps.notifications.periodic.cleanup_expired_otp_keys",
        "schedule": crontab(hour=3, minute=15),
    },
}

