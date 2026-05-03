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
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
]

LOCAL_APPS = [
    "apps.users",
    "apps.authentication",
    "apps.sorties",
    "apps.restaurants",
    "apps.bookings",
    "apps.events",
    "apps.public_events",
    "apps.partners",
    "apps.partner_opportunities",
    "apps.payments",
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
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
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

# ─── Password validation ───────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── Internationalisation ──────────────────────────────────────────────────────

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

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
