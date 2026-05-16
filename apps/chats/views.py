from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Chat, ChatParticipant, Message
from .serializers import ChatCreateSerializer, ChatSerializer, MessageSerializer


class ChatViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Chat.objects.filter(participants__user=self.request.user).distinct().order_by("-updated_at")

    def get_serializer_class(self):
        if self.action == "create":
            return ChatCreateSerializer
        return ChatSerializer

    @action(detail=True, methods=["get", "post"], url_path="messages")
    def messages(self, request, pk=None):
        chat = self.get_object()

        if request.method == "GET":
            queryset = chat.messages.select_related("sender").order_by("created_at")
            serializer = MessageSerializer(queryset, many=True)
            return Response(serializer.data)

        serializer = MessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = Message.objects.create(
            chat=chat,
            sender=request.user,
            content=serializer.validated_data["content"],
        )
        chat.save(update_fields=["updated_at"])
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="join")
    def join(self, request, pk=None):
        chat = self.get_object()
        ChatParticipant.objects.get_or_create(chat=chat, user=request.user)
        return Response({"detail": "Joined chat."}, status=status.HTTP_200_OK)
