from rest_framework import serializers

from .models import PartnerOpportunity


class PartnerOpportunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerOpportunity
        fields = ["id", "title", "description", "city", "category", "status", "created_at"]
