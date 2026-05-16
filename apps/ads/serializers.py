from rest_framework import serializers

from .models import SponsoredEvent


class SponsoredEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SponsoredEvent
        fields = [
            "id",
            "city",
            "event_id",
            "slot_name",
            "budget_eur",
            "starts_at",
            "ends_at",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
