"""
URL configuration for the Mooviogo Django project.
"""

from django.contrib import admin
from django.urls import include, path

API_PREFIX = "api/v1/"

urlpatterns = [
    path("admin/", admin.site.urls),
    # Health (before web catch-all)
    path("health/", include("apps.health.urls")),
    # REST API
    path(f"{API_PREFIX}auth/", include("apps.authentication.urls")),
    path(f"{API_PREFIX}users/", include("apps.users.urls")),
    path(f"{API_PREFIX}sorties/", include("apps.sorties.urls")),
    path(f"{API_PREFIX}restaurants/", include("apps.restaurants.urls")),
    path(f"{API_PREFIX}bookings/", include("apps.bookings.urls")),
    path(f"{API_PREFIX}events/", include("apps.events.urls")),
    path(f"{API_PREFIX}public-events/", include("apps.public_events.urls")),
    path(f"{API_PREFIX}partners/", include("apps.partners.urls")),
    path(f"{API_PREFIX}partner-opportunities/", include("apps.partner_opportunities.urls")),
    path(f"{API_PREFIX}payments/", include("apps.payments.urls")),
    path(f"{API_PREFIX}city-feed/", include("apps.city_feed.urls")),
    path(f"{API_PREFIX}reports/", include("apps.reports.urls")),
    # Web frontend (must be last — contains a catch-all <slug> route)
    path("", include("apps.web.urls")),
]
