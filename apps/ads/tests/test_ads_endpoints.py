from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.ads.models import SponsoredEvent

User = get_user_model()


class AdsEndpointsTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="ads-admin",
            email="ads-admin@example.com",
            password="strong-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        self.user = User.objects.create_user(
            username="ads-user",
            email="ads-user@example.com",
            password="strong-pass-123",
        )

    def test_public_can_list_active_sponsored_events(self):
        now = timezone.now()
        SponsoredEvent.objects.create(
            city="Paris",
            event_id=123,
            status=SponsoredEvent.Status.ACTIVE,
            starts_at=now,
            ends_at=now + timezone.timedelta(days=2),
        )

        response = self.client.get("/api/v1/ads/?active=1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        if isinstance(payload, dict) and "results" in payload:
            self.assertEqual(len(payload["results"]), 1)
        else:
            self.assertEqual(len(payload), 1)

    def test_non_admin_cannot_create_sponsored_event(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/ads/",
            {
                "city": "Paris",
                "event_id": 99,
                "budget_eur": 35,
                "starts_at": timezone.now().isoformat(),
                "ends_at": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
                "status": SponsoredEvent.Status.DRAFT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_sponsored_event(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/v1/ads/",
            {
                "city": "Lyon",
                "event_id": 100,
                "budget_eur": 50,
                "starts_at": timezone.now().isoformat(),
                "ends_at": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
                "status": SponsoredEvent.Status.DRAFT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
