from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.events.models import Event
from apps.partners.models import Partner
from apps.restaurants.models import RestaurantVenue
from apps.sorties.models import Sortie

User = get_user_model()


class PublicTemplateSmokeTests(TestCase):
    def setUp(self):
        self.sortie = Sortie.objects.create(
            title="Smoke sortie",
            slug="smoke-sortie",
            city="Paris",
            type=Sortie.Type.COMMUNAUTAIRE,
            status=Sortie.Status.OPEN,
            is_free=True,
            price=0,
        )
        self.event = Event.objects.create(
            title="Smoke event",
            slug="smoke-event",
            city="Paris",
            starts_at=timezone.now() + timezone.timedelta(days=1),
            status=Event.Status.PUBLISHED,
            is_partner_event=False,
        )
        self.venue = RestaurantVenue.objects.create(
            name="Smoke venue",
            slug="smoke-venue",
            city_slug="paris",
            city_label="Paris",
            is_active=True,
        )

    def test_public_pages_render(self):
        for path in [
            "/",
            "/explore/",
            "/events/",
            "/nightlife/",
            "/activities/",
            "/search/",
            "/pricing/",
            "/sorties/",
            f"/sorties/{self.sortie.pk}/",
            "/restaurants/",
            f"/restaurants/{self.venue.city_slug}/{self.venue.slug}/",
            "/evenements/",
            f"/evenements/{self.event.slug}/",
            "/villes/",
            "/ville/paris/",
            "/partenaires/",
            "/devenir-partenaire/",
            "/become-partner/",
            "/cgu/",
            "/confidentialite/",
            "/mentions-legales/",
            "/cookies/",
            "/faq/",
            "/a-propos/",
            "/contact/",
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, msg=f"Unexpected status for {path}")


class PartnerAdminTemplateAccessTests(TestCase):
    def setUp(self):
        self.partner_user = User.objects.create_user(
            username="partner-smoke",
            email="partner-smoke@example.com",
            password="strong-pass-123",
            is_partner=True,
            city="Paris",
        )
        Partner.objects.create(
            owner=self.partner_user,
            name="Partner Smoke",
            slug="partner-smoke",
            city="Paris",
            status=Partner.Status.ACTIVE,
        )

        self.staff_user = User.objects.create_user(
            username="staff-smoke",
            email="staff-smoke@example.com",
            password="strong-pass-123",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username="regular-smoke",
            email="regular-smoke@example.com",
            password="strong-pass-123",
        )

        self.sortie = Sortie.objects.create(
            title="Smoke sortie auth",
            slug="smoke-sortie-auth",
            city="Paris",
            type=Sortie.Type.COMMUNAUTAIRE,
            status=Sortie.Status.OPEN,
            creator=self.regular_user,
            is_free=True,
            price=0,
        )

        self.event = Event.objects.create(
            title="Smoke nightlife event",
            slug="smoke-nightlife-event",
            city="Paris",
            starts_at=timezone.now() + timezone.timedelta(days=1),
            status=Event.Status.PUBLISHED,
            is_partner_event=True,
            partner_id=Partner.objects.get(owner=self.partner_user).id,
        )

    def test_authenticated_user_pages_render(self):
        self.client.force_login(self.regular_user)
        for path in [
            "/profil/",
            "/profile/",
            "/messages/",
            "/notifications/",
            "/favorites/",
            "/my-events/",
            "/my-tickets/",
            "/settings/",
            "/profil/modifier/",
            "/profil/reservations/",
            "/create/free-event/",
            "/create/activity-request/",
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, msg=f"Unexpected status for {path}")

    def test_anonymous_on_protected_pages_redirects(self):
        for path in [
            "/profil/",
            "/messages/",
            "/sorties/creer/",
            "/partner/events/",
            "/nightlife/dashboard/",
            "/admin/",
        ]:
            response = self.client.get(path)
            self.assertIn(response.status_code, (302, 301), msg=f"Expected redirect for {path}")

    def test_partner_pages_render_for_partner_user(self):
        self.client.force_login(self.partner_user)
        for path in [
            "/partenaire/",
            "/partner/dashboard/",
            "/partner/analytics/",
            "/partner/events/",
            "/partner/events/create/",
            "/partner/bookings/",
            "/partner/requests/",
            "/partner/payments/",
            "/partner/settings/",
            "/nightlife/dashboard/",
            "/nightlife/events/",
            "/nightlife/events/create/",
            "/nightlife/analytics/",
            "/nightlife/tickets/",
            "/nightlife/tickets/scan/",
            "/nightlife/promotions/",
        ]:
            response = self.client.get(path, follow=True)
            self.assertEqual(response.status_code, 200, msg=f"Unexpected status for {path}")

    def test_admin_pages_render_for_staff_user(self):
        self.client.force_login(self.staff_user)
        for path in [
            "/admin/",
            "/admin/users/",
            "/admin/partners/",
            "/admin/events/",
            "/admin/reports/",
            "/admin/payments/",
            "/admin/ads/",
            "/admin/analytics/",
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, msg=f"Unexpected status for {path}")


class EnglishLocaleRenderingTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff-i18n",
            email="staff-i18n@example.com",
            password="strong-pass-123",
            is_staff=True,
        )

    def test_home_page_has_english_strings_when_language_is_en(self):
        self.client.cookies["django_language"] = "en"
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "I want to go out tonight")
        self.assertContains(response, "How it works")

    def test_partner_onboarding_page_has_english_strings_when_language_is_en(self):
        self.client.cookies["django_language"] = "en"
        response = self.client.get("/devenir-partenaire/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Become a partner")
        self.assertContains(response, "Start for free")

    def test_admin_page_has_english_strings_when_language_is_en(self):
        self.client.force_login(self.staff_user)
        self.client.cookies["django_language"] = "en"
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Platform administration")
        self.assertContains(response, "Total revenue")
