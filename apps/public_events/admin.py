from django.contrib import admin

from .models import PublicEvent


@admin.register(PublicEvent)
class PublicEventAdmin(admin.ModelAdmin):
    list_display = ["title", "city", "source", "starts_at", "status"]
    list_filter = ["status", "source", "city"]
    search_fields = ["title", "slug", "source_id"]
    date_hierarchy = "starts_at"
