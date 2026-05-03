from django.contrib import admin

from .models import RestaurantTimeSlot, RestaurantVenue


@admin.register(RestaurantVenue)
class RestaurantVenueAdmin(admin.ModelAdmin):
    list_display = ["name", "city_label", "cuisine_type", "price_range", "is_active"]
    list_filter = ["city_slug", "is_active"]
    search_fields = ["name", "slug", "city_label"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(RestaurantTimeSlot)
class RestaurantTimeSlotAdmin(admin.ModelAdmin):
    list_display = ["venue", "date", "time", "capacity", "confirmed_count", "status"]
    list_filter = ["status", "date"]
    date_hierarchy = "date"
