from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.partners.models import Partner
from apps.payments.models import Payment

User = get_user_model()


class PaymentsEndpointsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="payments-user",
            email="payments-user@example.com",
            password="strong-pass-123",
        )
        self.partner_user = User.objects.create_user(
            username="payments-partner",
            email="payments-partner@example.com",
            password="strong-pass-123",
            is_partner=True,
        )
        Partner.objects.create(
            owner=self.partner_user,
            name="Partner Payments",
            slug="partner-payments",
            city="Paris",
            email=self.partner_user.email,
            status=Partner.Status.ACTIVE,
        )

    @override_settings(STRIPE_SECRET_KEY="")
    def test_create_payment_intent_returns_503_when_stripe_not_configured(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/v1/payments/create-intent/",
            {"amount": 1500, "currency": "eur"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(Payment.objects.count(), 0)

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    @patch("apps.payments.views.stripe.PaymentIntent.create")
    def test_create_payment_intent_creates_payment_row(self, mock_create_intent):
        self.client.force_authenticate(self.user)
        mock_create_intent.return_value = SimpleNamespace(id="pi_test_123", client_secret="cs_test_123")

        response = self.client.post(
            "/api/v1/payments/create-intent/",
            {"amount": 2500, "currency": "eur"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["client_secret"], "cs_test_123")
        self.assertTrue(Payment.objects.filter(stripe_payment_intent_id="pi_test_123").exists())

    def test_connect_account_requires_partner_user(self):
        self.client.force_authenticate(self.user)

        response = self.client.post("/api/v1/payments/connect/account/")

        self.assertEqual(response.status_code, 403)
