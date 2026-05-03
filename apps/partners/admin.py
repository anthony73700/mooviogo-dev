from django.contrib import admin

from .models import Partner


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "category", "status", "is_verified", "created_at"]
    list_filter = ["status", "is_verified", "city"]
    search_fields = ["name", "slug", "email"]
    prepopulated_fields = {"slug": ("name",)}
