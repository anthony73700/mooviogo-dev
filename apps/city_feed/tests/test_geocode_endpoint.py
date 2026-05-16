import json
from unittest.mock import patch

from django.test import TestCase, override_settings


class GeocodeEndpointTests(TestCase):
    def _mock_response(self, payload):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        return _Resp()

    @patch("apps.city_feed.views.urllib.request.urlopen")
    def test_geocode_returns_normalized_results(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response(
            [
                {
                    "display_name": "12 Rue de la Republique, Lyon",
                    "lat": "45.764043",
                    "lon": "4.835659",
                    "address": {"city": "Lyon"},
                }
            ]
        )

        response = self.client.get("/api/v1/city-feed/geocode/?q=Rue+Republique&city=Lyon")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["city"], "Lyon")
        self.assertEqual(payload["results"][0]["latitude"], 45.764043)
        self.assertEqual(payload["results"][0]["longitude"], 4.835659)

    def test_geocode_requires_query(self):
        response = self.client.get("/api/v1/city-feed/geocode/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    @override_settings(GEOCODING_ENABLED=False)
    def test_geocode_disabled_returns_503(self):
        response = self.client.get("/api/v1/city-feed/geocode/?q=Paris")

        self.assertEqual(response.status_code, 503)
