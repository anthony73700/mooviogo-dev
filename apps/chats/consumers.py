from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Chat, ChatParticipant, Message


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.chat_id = int(self.scope["url_route"]["kwargs"]["chat_id"])
        if not await self._can_access_chat(user.id, self.chat_id):
            await self.close(code=4403)
            return

        self.room_group_name = f"chat_{self.chat_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        room_group = getattr(self, "room_group_name", None)
        if room_group:
            await self.channel_layer.group_discard(room_group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        if action != "message":
            await self.send_json({"type": "error", "detail": "Unsupported action."})
            return

        text = (content.get("content") or "").strip()
        if not text:
            await self.send_json({"type": "error", "detail": "Message is empty."})
            return

        message = await self._create_message(self.scope["user"].id, self.chat_id, text)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message",
                "message": message,
            },
        )

    async def chat_message(self, event):
        await self.send_json({"type": "message", "data": event["message"]})

    @database_sync_to_async
    def _can_access_chat(self, user_id, chat_id):
        return ChatParticipant.objects.filter(user_id=user_id, chat_id=chat_id).exists()

    @database_sync_to_async
    def _create_message(self, user_id, chat_id, content):
        chat = Chat.objects.get(id=chat_id)
        message = Message.objects.create(chat=chat, sender_id=user_id, content=content)
        return {
            "id": message.id,
            "chat_id": message.chat_id,
            "sender_id": message.sender_id,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        }
