from rest_framework import serializers

from .models import RestaurantTimeSlot, RestaurantVenue


class RestaurantVenueListSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantVenue
        fields = ["id", "name", "slug", "city_slug", "city_label", "cuisine_type", "price_range", "cover_image_url"]


class RestaurantVenueDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantVenue
        fields = "__all__"


class RestaurantTimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantTimeSlot
        fields = ["id", "date", "time", "capacity", "confirmed_count", "status"]
        read_only_fields = ["confirmed_count"]
