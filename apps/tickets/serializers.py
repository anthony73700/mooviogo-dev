from rest_framework import serializers

from .models import Ticket, TicketScanAudit


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = [
            "id",
            "user",
            "booking_id",
            "event_id",
            "sortie_id",
            "qr_token",
            "qr_payload",
            "status",
            "used_at",
            "created_at",
        ]
        read_only_fields = ["id", "user", "qr_token", "qr_payload", "used_at", "created_at"]


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ["booking_id", "event_id", "sortie_id"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        validated_data["status"] = Ticket.Status.ACTIVE
        return super().create(validated_data)


class TicketValidateSerializer(serializers.Serializer):
    qr_token = serializers.CharField(max_length=64)
    source = serializers.ChoiceField(choices=TicketScanAudit.Source.choices, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class TicketScanAuditSerializer(serializers.ModelSerializer):
    operator_email = serializers.EmailField(source="operator.email", read_only=True)

    class Meta:
        model = TicketScanAudit
        fields = [
            "id",
            "ticket",
            "operator",
            "operator_email",
            "scanned_token",
            "outcome",
            "reason_code",
            "source",
            "operator_city",
            "target_city",
            "notes",
            "created_at",
        ]
        read_only_fields = fields
