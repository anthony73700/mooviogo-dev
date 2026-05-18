from django.conf import settings

from apps.partners.models import Partner
from apps.restaurants.models import RestaurantVenue


def site_config(request):
    is_pro_account = False
    if getattr(request, "user", None) and request.user.is_authenticated:
        is_pro_account = bool(
            (not request.user.is_staff and not request.user.is_superuser)
            and (
                request.user.is_partner
                or Partner.objects.filter(owner=request.user).exists()
                or RestaurantVenue.objects.filter(owner=request.user, is_active=True).exists()
            )
        )

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
        "IS_PRO_ACCOUNT": is_pro_account,
        "PRO_DASHBOARD_URL": "/partenaire/",
    }
