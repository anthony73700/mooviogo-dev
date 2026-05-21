from django.contrib import admin

from .models import RestaurantTimeSlot, RestaurantVenue, RestaurantVenuePhoto


class RestaurantVenuePhotoInline(admin.TabularInline):
    model = RestaurantVenuePhoto
    extra = 1
    fields = ["position", "image_url", "caption", "is_active"]
    ordering = ["position", "id"]


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
    inlines = [RestaurantVenuePhotoInline]


@admin.register(RestaurantTimeSlot)
class RestaurantTimeSlotAdmin(admin.ModelAdmin):
    list_display = ["venue", "date", "time", "capacity", "confirmed_count", "status"]
    list_filter = ["status", "date"]
    date_hierarchy = "date"


@admin.register(RestaurantVenuePhoto)
class RestaurantVenuePhotoAdmin(admin.ModelAdmin):
    list_display = ["venue", "position", "caption", "is_active", "created_at"]
    list_filter = ["is_active", "venue__city_slug"]
    search_fields = ["venue__name", "caption", "image_url"]
    list_select_related = ["venue"]
    ordering = ["venue", "position", "id"]
