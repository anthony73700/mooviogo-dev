from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Chat, ChatParticipant, Message

User = get_user_model()


class ChatParticipantSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="user.display_name", read_only=True)

    class Meta:
        model = ChatParticipant
        fields = ["id", "user", "display_name", "joined_at"]
        read_only_fields = ["id", "joined_at", "display_name"]


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.display_name", read_only=True)

    class Meta:
        model = Message
        fields = ["id", "chat", "sender", "sender_name", "content", "created_at"]
        read_only_fields = ["id", "sender", "sender_name", "created_at"]


class ChatSerializer(serializers.ModelSerializer):
    participants = ChatParticipantSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = [
            "id",
            "type",
            "name",
            "event_id",
            "sortie_id",
            "participants",
            "last_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "last_message", "participants"]

    def get_last_message(self, obj):
        message = obj.messages.order_by("-created_at").first()
        if not message:
            return None
        return {
            "id": message.id,
            "content": message.content,
            "sender_id": message.sender_id,
            "created_at": message.created_at,
        }


class ChatCreateSerializer(serializers.ModelSerializer):
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Chat
        fields = ["type", "name", "event_id", "sortie_id", "participant_ids"]

    def create(self, validated_data):
        participant_ids = validated_data.pop("participant_ids", [])
        request = self.context["request"]
        chat = Chat.objects.create(created_by=request.user, **validated_data)

        ChatParticipant.objects.get_or_create(chat=chat, user=request.user)

        if participant_ids:
            users = User.objects.filter(id__in=participant_ids)
            for user in users:
                ChatParticipant.objects.get_or_create(chat=chat, user=user)

        return chat
