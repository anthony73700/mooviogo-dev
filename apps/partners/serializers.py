from rest_framework import serializers

from .models import Partner


class PartnerListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = ["id", "name", "slug", "city", "category", "short_description", "cover_image_url", "is_verified"]


class PartnerDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        exclude = ["owner"]
