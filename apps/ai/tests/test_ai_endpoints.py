from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

User = get_user_model()


class AIEndpointsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ai-user",
            email="ai-user@example.com",
            password="strong-pass-123",
        )

    def test_recommendations_is_public(self):
        response = self.client.post(
            "/api/v1/ai/recommendations/",
            {"city": "Paris"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("recommended_sorties", body)
        self.assertIn("recommended_events", body)

    def test_create_post_requires_authentication(self):
        response = self.client.post(
            "/api/v1/ai/create-post/",
            {"event_title": "Soiree rooftop", "tone": "nightlife"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_create_post_returns_generated_content_for_authenticated_user(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/ai/create-post/",
            {"event_title": "Soiree rooftop", "tone": "nightlife", "city": "Paris"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("post", response.json())
        self.assertIn("hashtags", response.json())

    def test_create_event_requires_authentication(self):
        response = self.client.post(
            "/api/v1/ai/create-event/",
            {"city": "Paris", "category": "afterwork"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
