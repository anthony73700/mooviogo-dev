from django.conf import settings


def site_config(request):
    return {
        "APP_BASE_URL": settings.APP_BASE_URL.rstrip("/"),
        "ENABLE_ANALYTICS": bool(getattr(settings, "ENABLE_ANALYTICS", False)),
        "GA4_MEASUREMENT_ID": getattr(settings, "GA4_MEASUREMENT_ID", ""),
        "POSTHOG_KEY": getattr(settings, "POSTHOG_KEY", ""),
        "POSTHOG_HOST": getattr(settings, "POSTHOG_HOST", ""),
        "META_PIXEL_ID": getattr(settings, "META_PIXEL_ID", ""),
        "TIKTOK_PIXEL_ID": getattr(settings, "TIKTOK_PIXEL_ID", ""),
        "GOOGLE_MAPS_API_KEY": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
        "TURNSTILE_SITE_KEY": getattr(settings, "TURNSTILE_SITE_KEY", ""),
    }
