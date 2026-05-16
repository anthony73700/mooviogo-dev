import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.chats.consumers import ChatConsumer
from apps.chats.models import Chat, ChatParticipant

User = get_user_model()


class ChatConsumerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ws-user",
            email="ws-user@example.com",
            password="strong-pass-123",
        )
        self.other_user = User.objects.create_user(
            username="ws-other",
            email="ws-other@example.com",
            password="strong-pass-123",
        )
        self.chat = Chat.objects.create(type=Chat.Type.GROUP, name="WS chat", created_by=self.user)
        ChatParticipant.objects.create(chat=self.chat, user=self.user)

    def _build_consumer(self, user, chat_id):
        consumer = ChatConsumer()
        consumer.scope = {
            "user": user,
            "url_route": {"kwargs": {"chat_id": str(chat_id)}},
        }
        consumer.channel_name = "test-channel"
        consumer.channel_layer = SimpleNamespace(
            group_add=AsyncMock(),
            group_discard=AsyncMock(),
            group_send=AsyncMock(),
        )
        consumer.accept = AsyncMock()
        consumer.close = AsyncMock()
        consumer.send_json = AsyncMock()
        return consumer

    def test_connect_rejects_anonymous_user(self):
        anon = SimpleNamespace(is_authenticated=False)
        consumer = self._build_consumer(anon, self.chat.id)

        asyncio.run(consumer.connect())

        consumer.close.assert_awaited_once_with(code=4401)
        consumer.accept.assert_not_awaited()

    def test_connect_rejects_user_outside_chat_scope(self):
        consumer = self._build_consumer(self.other_user, self.chat.id)
        consumer._can_access_chat = AsyncMock(return_value=False)

        asyncio.run(consumer.connect())

        consumer.close.assert_awaited_once_with(code=4403)
        consumer.accept.assert_not_awaited()

    def test_connect_accepts_chat_participant(self):
        consumer = self._build_consumer(self.user, self.chat.id)
        consumer._can_access_chat = AsyncMock(return_value=True)

        asyncio.run(consumer.connect())

        consumer.accept.assert_awaited_once()
        consumer.channel_layer.group_add.assert_awaited_once_with("chat_%s" % self.chat.id, "test-channel")

    def test_receive_json_rejects_unsupported_action(self):
        consumer = self._build_consumer(self.user, self.chat.id)

        asyncio.run(consumer.receive_json({"action": "typing"}))

        consumer.send_json.assert_awaited_once_with({"type": "error", "detail": "Unsupported action."})

    def test_receive_json_rejects_empty_message(self):
        consumer = self._build_consumer(self.user, self.chat.id)

        asyncio.run(consumer.receive_json({"action": "message", "content": "   "}))

        consumer.send_json.assert_awaited_once_with({"type": "error", "detail": "Message is empty."})

    def test_receive_json_sends_message_to_group(self):
        consumer = self._build_consumer(self.user, self.chat.id)
        consumer.chat_id = self.chat.id
        consumer.room_group_name = f"chat_{self.chat.id}"
        consumer._create_message = AsyncMock(
            return_value={
                "id": 1,
                "chat_id": self.chat.id,
                "sender_id": self.user.id,
                "content": "hello",
                "created_at": "2026-05-16T00:00:00+00:00",
            }
        )

        asyncio.run(consumer.receive_json({"action": "message", "content": "hello"}))

        consumer.channel_layer.group_send.assert_awaited_once()
        sent_payload = consumer.channel_layer.group_send.await_args.args[1]
        self.assertEqual(sent_payload["type"], "chat.message")
        self.assertEqual(sent_payload["message"]["content"], "hello")
