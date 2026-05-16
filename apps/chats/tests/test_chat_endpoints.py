from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.chats.models import Chat, ChatParticipant

User = get_user_model()


class ChatEndpointsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="chat-user",
            email="chat-user@example.com",
            password="strong-pass-123",
        )

    def test_anonymous_user_cannot_list_chats(self):
        response = self.client.get("/api/v1/chats/")
        self.assertEqual(response.status_code, 401)

    def test_authenticated_user_can_create_and_list_own_chat(self):
        self.client.force_authenticate(self.user)

        create_response = self.client.post(
            "/api/v1/chats/",
            {"type": "GROUP", "name": "Team chat"},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        chat_id = Chat.objects.get(name="Team chat").id

        self.assertTrue(ChatParticipant.objects.filter(chat_id=chat_id, user=self.user).exists())

        list_response = self.client.get("/api/v1/chats/")
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        if isinstance(payload, dict) and "results" in payload:
            self.assertEqual(len(payload["results"]), 1)
        else:
            self.assertEqual(len(payload), 1)
