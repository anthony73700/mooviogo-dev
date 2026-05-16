from django.test import TestCase
from django.templatetags.static import static
from pathlib import Path


class SeoAndDocsRoutesTests(TestCase):
    def test_robots_txt_is_available(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sitemap:", response.content.decode("utf-8"))

    def test_sitemap_xml_is_available(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn("<urlset", response.content.decode("utf-8"))

    def test_openapi_schema_and_docs_are_available(self):
        schema_response = self.client.get("/api/schema/")
        docs_response = self.client.get("/api/docs/")

        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(docs_response.status_code, 200)
        self.assertIn("swagger-ui", docs_response.content.decode("utf-8").lower())

    def test_i18n_set_language_route_is_available(self):
        response = self.client.post("/i18n/setlang/", {"language": "en", "next": "/"}, follow=False)
        self.assertIn(response.status_code, {302, 303})

    def test_default_og_static_asset_exists(self):
        path = Path("/home/debian/mooviogo-dev/apps/web/static/og/default-og.svg")
        self.assertTrue(path.exists())
        self.assertTrue(static("og/default-og.svg").endswith("og/default-og.svg"))
