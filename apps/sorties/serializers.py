from rest_framework import serializers

from .models import Sortie, SortieParticipant


class SortieListSerializer(serializers.ModelSerializer):
    participant_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Sortie
        fields = [
            "id", "title", "slug", "city", "type", "status",
            "starts_at", "price", "is_free", "cover_image_url",
            "participant_count",
        ]


class SortieDetailSerializer(serializers.ModelSerializer):
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = Sortie
        fields = [
            "id", "title", "slug", "description", "city", "location",
            "type", "status", "price", "currency", "is_free",
            "max_participants", "starts_at", "cover_image_url",
            "participant_count", "created_at",
        ]

    def get_participant_count(self, obj):
        return obj.participants.filter(status=SortieParticipant.ParticipationStatus.CONFIRMED).count()


class SortieCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sortie
        fields = [
            "title", "slug", "description", "city", "location",
            "type", "starts_at", "cover_image_url", "max_participants",
        ]

    def create(self, validated_data):
        validated_data["creator"] = self.context["request"].user
        validated_data["price"] = 0
        validated_data["is_free"] = True
        return super().create(validated_data)


class SortieParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = SortieParticipant
        fields = ["id", "sortie", "user", "status", "joined_at"]
        read_only_fields = ["id", "joined_at"]
