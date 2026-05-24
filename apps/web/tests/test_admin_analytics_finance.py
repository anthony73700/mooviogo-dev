from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.bookings.models import Booking
from apps.events.models import Event
from apps.partners.models import Partner
from apps.payments.models import Payment
from apps.restaurants.models import RestaurantTimeSlot, RestaurantVenue
from apps.sorties.models import Sortie

User = get_user_model()


class AdminAnalyticsFinanceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-finance",
            email="admin-finance@example.com",
            password="strong-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        self.customer = User.objects.create_user(
            username="cust-finance",
            email="cust-finance@example.com",
            password="strong-pass-123",
            city="Paris",
        )

        self.partner = Partner.objects.create(
            owner=self.customer,
            name="Partner Finance",
            slug="partner-finance",
            city="Paris",
            status=Partner.Status.ACTIVE,
        )

        self.sortie = Sortie.objects.create(
            creator=self.customer,
            partner=self.partner,
            title="Sortie Test",
            slug="sortie-test-finance",
            city="Paris",
            type=Sortie.Type.PARTENAIRE,
            status=Sortie.Status.OPEN,
            price=1000,
            is_free=False,
        )
        self.booking_sortie = Booking.objects.create(
            user=self.customer,
            booking_type=Booking.BookingType.SORTIE,
            sortie_id=self.sortie.id,
            status=Booking.Status.CONFIRMED,
            amount=10000,
        )

        self.venue = RestaurantVenue.objects.create(
            name="Bistro Lyon",
            slug="bistro-lyon-finance",
            city_slug="lyon",
            city_label="Lyon",
            is_active=True,
        )
        self.slot = RestaurantTimeSlot.objects.create(
            venue=self.venue,
            date="2030-02-01",
            time="20:00",
            capacity=4,
            confirmed_count=1,
            status=RestaurantTimeSlot.SlotStatus.OPEN,
        )
        self.booking_restaurant = Booking.objects.create(
            user=self.customer,
            booking_type=Booking.BookingType.RESTAURANT,
            restaurant_slot_id=self.slot.id,
            status=Booking.Status.CONFIRMED,
            amount=5000,
        )

        self.event = Event.objects.create(
            title="Event Paris",
            slug="event-paris-finance",
            city="Paris",
            starts_at="2030-01-01T20:00:00Z",
            status=Event.Status.PUBLISHED,
        )

        Payment.objects.create(
            user=self.customer,
            booking_id=self.booking_sortie.id,
            amount=10000,
            currency="EUR",
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_finance_sortie",
        )
        Payment.objects.create(
            user=self.customer,
            booking_id=self.booking_restaurant.id,
            amount=5000,
            currency="EUR",
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_finance_restaurant",
        )

    def test_admin_analytics_exposes_finance_kpis_and_city_rows(self):
        self.client.force_login(self.admin)

        response = self.client.get("/admin/analytics/?period=month")

        self.assertEqual(response.status_code, 200)
        kpis = response.context["kpis"]
        self.assertGreater(kpis["commission_cents"], 0)
        self.assertGreater(kpis["processing_fees_cents"], 0)
        self.assertGreater(kpis["tax_cents"], 0)
        self.assertGreaterEqual(kpis["platform_net_cents"], 0)

        city_rows = response.context["city_rows"]
        cities = {row["city"] for row in city_rows}
        self.assertIn("Paris", cities)
        self.assertIn("Lyon", cities)

        source_rows = response.context["source_rows"]
        sources = {row["source"] for row in source_rows}
        self.assertIn("sortie", sources)
        self.assertIn("restaurant", sources)

    def test_admin_analytics_csv_contains_finance_columns(self):
        self.client.force_login(self.admin)

        response = self.client.get("/admin/analytics/?period=month&export=csv")

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("processing_fees_cents", content)
        self.assertIn("platform_net_cents", content)
