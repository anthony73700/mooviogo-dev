from django.contrib import admin

from .models import RestaurantTimeSlot, RestaurantVenue


@admin.register(RestaurantVenue)
class RestaurantVenueAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "city_label",
        "owner",
        "reservation_mode",
        "editorial_boost_amount",
        "editorial_boost_ends_at",
        "cuisine_type",
        "price_range",
        "is_active",
    ]
    list_filter = ["city_slug", "reservation_mode", "is_active", "editorial_boost_ends_at"]
    search_fields = ["name", "slug", "city_label"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(RestaurantTimeSlot)
class RestaurantTimeSlotAdmin(admin.ModelAdmin):
    list_display = ["venue", "date", "time", "capacity", "confirmed_count", "status"]
    list_filter = ["status", "date"]
    date_hierarchy = "date"
