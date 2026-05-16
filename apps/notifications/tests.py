from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import WebPushSubscription

User = get_user_model()


class NotificationsAccessTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-notif",
            email="admin-notif@example.com",
            password="strong-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        self.user = User.objects.create_user(
            username="user-notif",
            email="user-notif@example.com",
            password="strong-pass-123",
        )

    def test_non_admin_cannot_send_notifications(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/notifications/send/",
            {
                "channel": "email",
                "to": "target@example.com",
                "subject": "Hello",
                "message": "World",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_accepts_sms_channel_and_queues_notification(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/v1/notifications/send/",
            {
                "channel": "sms",
                "to": "+33123456789",
                "message": "Ping",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data.get("channel"), "sms")
        self.assertEqual(response.data.get("status"), "queued")

    def test_authenticated_user_can_subscribe_web_push(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/notifications/web-push/subscription/",
            {
                "endpoint": "https://push.example.test/subscription/abc",
                "keys": {
                    "p256dh": "test-p256dh-key",
                    "auth": "test-auth-key",
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(WebPushSubscription.objects.filter(user=self.user, is_active=True).count(), 1)

    def test_anonymous_user_cannot_subscribe_web_push(self):
        response = self.client.post(
            "/api/v1/notifications/web-push/subscription/",
            {
                "endpoint": "https://push.example.test/subscription/abc",
                "keys": {
                    "p256dh": "test-p256dh-key",
                    "auth": "test-auth-key",
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
