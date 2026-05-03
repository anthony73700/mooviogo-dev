from rest_framework import serializers

from .models import PublicEvent


class PublicEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicEvent
        fields = [
            "id", "title", "slug", "city", "location",
            "starts_at", "ends_at", "cover_image_url", "external_url",
            "status", "source",
        ]
