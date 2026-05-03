from rest_framework import serializers

from .models import Event


class EventListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "title", "slug", "city", "starts_at", "price", "cover_image_url", "status"]


class EventDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = "__all__"


class EventCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "title", "slug", "description", "city", "location",
            "starts_at", "ends_at", "cover_image_url", "price",
            "max_participants",
        ]
