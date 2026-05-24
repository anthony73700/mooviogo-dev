"""
URL configuration for the Mooviogo Django project.
"""

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework.schemas import get_schema_view

from apps.web.views import api_docs_page
from apps.web.views import set_language_and_preference

API_PREFIX = "api/v1/"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("i18n/setlang/", set_language_and_preference, name="set_language"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("api/schema/", get_schema_view(title="Mooviogo API"), name="api-schema"),
    path("api/docs/", api_docs_page, name="api-docs"),
    # Health (before web catch-all)
    path("health/", include("apps.health.urls")),
    # REST API
    path(f"{API_PREFIX}auth/", include("apps.authentication.urls")),
    path(f"{API_PREFIX}users/", include("apps.users.urls")),
    path(f"{API_PREFIX}sorties/", include("apps.sorties.urls")),
    path(f"{API_PREFIX}restaurants/", include("apps.restaurants.urls")),
    path(f"{API_PREFIX}bookings/", include("apps.bookings.urls")),
    path(f"{API_PREFIX}events/", include("apps.events.urls")),
    path(f"{API_PREFIX}chats/", include("apps.chats.urls")),
    path(f"{API_PREFIX}public-events/", include("apps.public_events.urls")),
    path(f"{API_PREFIX}partners/", include("apps.partners.urls")),
    path(f"{API_PREFIX}partner-opportunities/", include("apps.partner_opportunities.urls")),
    path(f"{API_PREFIX}tickets/", include("apps.tickets.urls")),
    path(f"{API_PREFIX}payments/", include("apps.payments.urls")),
    path(f"{API_PREFIX}ads/", include("apps.ads.urls")),
    path(f"{API_PREFIX}notifications/", include("apps.notifications.urls")),
    path(f"{API_PREFIX}ai/", include("apps.ai.urls")),
    path(f"{API_PREFIX}city-feed/", include("apps.city_feed.urls")),
    path(f"{API_PREFIX}reports/", include("apps.reports.urls")),
    # Web frontend (must be last — contains a catch-all <slug> route)
    path("", include("apps.web.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
