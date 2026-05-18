from django.contrib import admin

from .models import Sortie, SortieParticipant


@admin.register(Sortie)
class SortieAdmin(admin.ModelAdmin):
    list_display = ["title", "city", "partner", "type", "status", "is_free", "starts_at", "created_at"]
    list_filter = ["type", "status", "is_free", "city", "partner"]
    search_fields = ["title", "slug", "city"]
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "created_at"


@admin.register(SortieParticipant)
class SortieParticipantAdmin(admin.ModelAdmin):
    list_display = ["user", "sortie", "status", "joined_at"]
    list_filter = ["status"]
