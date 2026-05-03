from rest_framework import serializers

from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = [
            "id", "booking_type", "sortie_id", "restaurant_slot_id",
            "activity_session_id", "status", "amount", "currency",
            "created_at",
        ]
        read_only_fields = ["id", "status", "stripe_payment_intent_id", "created_at"]


class BookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ["booking_type", "sortie_id", "restaurant_slot_id", "activity_session_id"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)
