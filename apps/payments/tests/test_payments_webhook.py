from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.tickets.models import Ticket

User = get_user_model()


class StripeWebhookTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="webhook-user",
            email="webhook-user@example.com",
            password="strong-pass-123",
        )

    def _post_webhook(self):
        return self.client.post(
            "/api/v1/payments/webhook/stripe/",
            data="{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig_test",
        )

    @patch("apps.payments.views.stripe.Webhook.construct_event")
    def test_webhook_succeeded_updates_payment_booking_and_ticket(self, mock_construct_event):
        booking = Booking.objects.create(
            user=self.user,
            booking_type=Booking.BookingType.SORTIE,
            status=Booking.Status.PENDING,
            amount=1200,
        )
        payment = Payment.objects.create(
            user=self.user,
            booking_id=booking.id,
            amount=1200,
            currency="EUR",
            status=Payment.Status.PENDING,
            stripe_payment_intent_id="pi_succeeded_1",
        )

        mock_construct_event.return_value = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_succeeded_1",
                    "latest_charge": "ch_123",
                }
            },
        }

        response = self._post_webhook()

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(payment.stripe_charge_id, "ch_123")
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(booking.stripe_payment_intent_id, "pi_succeeded_1")
        self.assertTrue(
            Ticket.objects.filter(
                user=self.user,
                booking_id=booking.id,
                status=Ticket.Status.ACTIVE,
            ).exists()
        )

    @patch("apps.payments.views.stripe.Webhook.construct_event")
    def test_webhook_failed_marks_payment_failed_and_booking_cancelled(self, mock_construct_event):
        booking = Booking.objects.create(
            user=self.user,
            booking_type=Booking.BookingType.SORTIE,
            status=Booking.Status.PENDING,
            amount=1500,
        )
        payment = Payment.objects.create(
            user=self.user,
            booking_id=booking.id,
            amount=1500,
            currency="EUR",
            status=Payment.Status.PENDING,
            stripe_payment_intent_id="pi_failed_1",
        )

        mock_construct_event.return_value = {
            "type": "payment_intent.payment_failed",
            "data": {
                "object": {
                    "id": "pi_failed_1",
                }
            },
        }

        response = self._post_webhook()

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(booking.status, Booking.Status.CANCELLED)

    @patch("apps.payments.views.stripe.Webhook.construct_event", side_effect=ValueError("bad payload"))
    def test_webhook_returns_400_on_invalid_event(self, _mock_construct_event):
        response = self._post_webhook()
        self.assertEqual(response.status_code, 400)
