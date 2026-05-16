from django.contrib.auth import get_user_model
from django.test import TestCase


User = get_user_model()


class LanguagePreferenceTests(TestCase):
    def test_accept_language_header_auto_detects_english_for_anonymous(self):
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "I want to go out tonight")

    def test_set_language_persists_authenticated_user_preference(self):
        user = User.objects.create_user(
            username="lang-user",
            email="lang-user@example.com",
            password="strong-pass-123",
        )
        self.client.force_login(user)

        response = self.client.post("/i18n/setlang/", {"language": "en", "next": "/"}, follow=False)

        self.assertIn(response.status_code, {302, 303})
        user.refresh_from_db()
        self.assertEqual(user.preferred_language, "en")

    def test_saved_user_preference_overrides_missing_cookie(self):
        user = User.objects.create_user(
            username="lang-user-pref",
            email="lang-user-pref@example.com",
            password="strong-pass-123",
            preferred_language="en",
        )
        self.client.force_login(user)
        self.client.cookies.pop("django_language", None)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "I want to go out tonight")
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")

    def test_set_language_persists_spanish_for_authenticated_user(self):
        user = User.objects.create_user(
            username="lang-user-es",
            email="lang-user-es@example.com",
            password="strong-pass-123",
        )
        self.client.force_login(user)

        response = self.client.post("/i18n/setlang/", {"language": "es", "next": "/"}, follow=False)

        self.assertIn(response.status_code, {302, 303})
        user.refresh_from_db()
        self.assertEqual(user.preferred_language, "es")

    def test_saved_spanish_preference_applies_language_code(self):
        user = User.objects.create_user(
            username="lang-user-pref-es",
            email="lang-user-pref-es@example.com",
            password="strong-pass-123",
            preferred_language="es",
        )
        self.client.force_login(user)
        self.client.cookies.pop("django_language", None)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "es")

    def test_home_page_renders_spanish_navigation_label(self):
        self.client.cookies["django_language"] = "es"

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Iniciar sesion")
