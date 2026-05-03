from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "display_name", "city", "is_partner", "is_verified", "is_staff"]
    list_filter = ["is_partner", "is_verified", "is_staff", "is_active"]
    search_fields = ["email", "display_name", "username"]
    ordering = ["-created_at"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Mooviogo", {"fields": ("display_name", "avatar_url", "bio", "city", "is_partner", "is_verified")}),
    )
