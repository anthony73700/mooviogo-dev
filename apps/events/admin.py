from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "city", "starts_at", "status", "is_partner_event"]
    list_filter = ["status", "city", "is_partner_event"]
    search_fields = ["title", "slug"]
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "starts_at"
