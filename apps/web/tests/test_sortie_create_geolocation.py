from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.sorties.models import Sortie

User = get_user_model()


class SortieCreateGeolocationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sortie-owner",
            email="sortie-owner@example.com",
            password="strong-pass-123",
        )

    def test_create_sortie_persists_location_and_coordinates(self):
        self.client.force_login(self.user)
        title = f"Footing geoloc {uuid4().hex[:8]}"

        response = self.client.post(
            "/sorties/creer/",
            {
                "title": title,
                "description": "Session running",
                "city": "Lyon",
                "location": "Parc de la Tete d Or",
                "latitude": "45.779660",
                "longitude": "4.855400",
                "type": Sortie.Type.COMMUNAUTAIRE,
                "is_free": "on",
                "price": "0",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        sortie = Sortie.objects.get(title=title)
        self.assertEqual(sortie.location, "Parc de la Tete d Or")
        self.assertEqual(float(sortie.latitude), 45.77966)
        self.assertEqual(float(sortie.longitude), 4.8554)

    def test_create_sortie_rejects_invalid_coordinates(self):
        self.client.force_login(self.user)

        response = self.client.post(
            "/sorties/creer/",
            {
                "title": "Sortie invalide",
                "city": "Lyon",
                "latitude": "999",
                "longitude": "181",
                "type": Sortie.Type.COMMUNAUTAIRE,
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Latitude invalide")
        self.assertContains(response, "Longitude invalide")
        self.assertFalse(Sortie.objects.filter(title="Sortie invalide").exists())
