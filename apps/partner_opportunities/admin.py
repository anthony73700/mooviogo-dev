from django.contrib import admin

from .models import PartnerOpportunity


@admin.register(PartnerOpportunity)
class PartnerOpportunityAdmin(admin.ModelAdmin):
    list_display = ["title", "city", "category", "status", "created_at"]
    list_filter = ["status", "city"]
    search_fields = ["title", "description"]
