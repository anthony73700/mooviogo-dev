import stripe
from django.conf import settings
from rest_framework import permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking
from apps.partners.models import Partner
from apps.tickets.models import Ticket

from .models import Payment


class StripeConnectAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_partner:
            return Response({"detail": "Partner account required."}, status=status.HTTP_403_FORBIDDEN)

        partner = Partner.objects.filter(owner=request.user).first()
        if not partner:
            return Response({"detail": "Partner profile not found."}, status=status.HTTP_404_NOT_FOUND)

        if not settings.STRIPE_SECRET_KEY:
            return Response({"detail": "Stripe is not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        stripe.api_key = settings.STRIPE_SECRET_KEY

        if partner.stripe_connect_account_id:
            return Response(
                {"account_id": partner.stripe_connect_account_id, "already_exists": True},
                status=status.HTTP_200_OK,
            )

        account = stripe.Account.create(
            type="express",
            country="FR",
            email=partner.email or request.user.email,
            business_type="individual",
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            metadata={"partner_id": str(partner.id), "user_id": str(request.user.id)},
        )

        partner.stripe_connect_account_id = account.id
        partner.save(update_fields=["stripe_connect_account_id", "updated_at"])
        return Response({"account_id": account.id}, status=status.HTTP_201_CREATED)


class StripeConnectOnboardingLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_partner:
            return Response({"detail": "Partner account required."}, status=status.HTTP_403_FORBIDDEN)

        partner = Partner.objects.filter(owner=request.user).first()
        if not partner or not partner.stripe_connect_account_id:
            return Response({"detail": "Connect account not initialized."}, status=status.HTTP_400_BAD_REQUEST)

        if not settings.STRIPE_SECRET_KEY:
            return Response({"detail": "Stripe is not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        stripe.api_key = settings.STRIPE_SECRET_KEY
        account_link = stripe.AccountLink.create(
            account=partner.stripe_connect_account_id,
            refresh_url=f"{settings.APP_BASE_URL}/partner/settings/",
            return_url=f"{settings.APP_BASE_URL}/partner/payments/",
            type="account_onboarding",
        )
        return Response({"url": account_link.url}, status=status.HTTP_201_CREATED)


class StripeConnectStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_partner:
            return Response({"detail": "Partner account required."}, status=status.HTTP_403_FORBIDDEN)

        partner = Partner.objects.filter(owner=request.user).first()
        if not partner:
            return Response({"detail": "Partner profile not found."}, status=status.HTTP_404_NOT_FOUND)

        if not partner.stripe_connect_account_id:
            return Response({"is_connected": False}, status=status.HTTP_200_OK)

        if not settings.STRIPE_SECRET_KEY:
            return Response({"detail": "Stripe is not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        stripe.api_key = settings.STRIPE_SECRET_KEY
        account = stripe.Account.retrieve(partner.stripe_connect_account_id)

        partner.stripe_connect_details_submitted = bool(account.get("details_submitted"))
        partner.stripe_connect_charges_enabled = bool(account.get("charges_enabled"))
        partner.stripe_connect_payouts_enabled = bool(account.get("payouts_enabled"))
        partner.stripe_connect_onboarded = (
            partner.stripe_connect_details_submitted
            and partner.stripe_connect_charges_enabled
            and partner.stripe_connect_payouts_enabled
        )
        partner.save(
            update_fields=[
                "stripe_connect_details_submitted",
                "stripe_connect_charges_enabled",
                "stripe_connect_payouts_enabled",
                "stripe_connect_onboarded",
                "updated_at",
            ]
        )

        return Response(
            {
                "is_connected": True,
                "account_id": partner.stripe_connect_account_id,
                "onboarded": partner.stripe_connect_onboarded,
                "details_submitted": partner.stripe_connect_details_submitted,
                "charges_enabled": partner.stripe_connect_charges_enabled,
                "payouts_enabled": partner.stripe_connect_payouts_enabled,
            },
            status=status.HTTP_200_OK,
        )


class CreatePaymentIntentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        amount = request.data.get("amount")
        currency = request.data.get("currency", "eur")
        booking_id = request.data.get("booking_id")

        if not amount or not isinstance(amount, int) or amount <= 0:
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)

        if not settings.STRIPE_SECRET_KEY:
            return Response({"detail": "Stripe is not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        stripe.api_key = settings.STRIPE_SECRET_KEY

        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            # Surface Apple Pay / Google Pay / Cards automatiquement côté client
            automatic_payment_methods={"enabled": True},
            metadata={"user_id": str(request.user.id), "booking_id": str(booking_id or "")},
        )

        Payment.objects.create(
            user=request.user,
            booking_id=booking_id,
            amount=amount,
            currency=currency.upper(),
            stripe_payment_intent_id=intent.id,
        )

        return Response({"client_secret": intent.client_secret}, status=status.HTTP_201_CREATED)


class StripeWebhookView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if event["type"] == "payment_intent.succeeded":
            pi = event["data"]["object"]
            payment = Payment.objects.filter(stripe_payment_intent_id=pi["id"]).first()
            if payment:
                payment.status = Payment.Status.SUCCEEDED
                payment.stripe_charge_id = pi.get("latest_charge", "")
                payment.save(update_fields=["status", "stripe_charge_id", "updated_at"])

                if payment.booking_id:
                    booking = Booking.objects.filter(id=payment.booking_id).first()
                    if booking:
                        booking.status = Booking.Status.CONFIRMED
                        booking.stripe_payment_intent_id = pi["id"]
                        booking.save(update_fields=["status", "stripe_payment_intent_id", "updated_at"])

                        Ticket.objects.get_or_create(
                            user=booking.user,
                            booking_id=booking.id,
                            defaults={
                                "status": Ticket.Status.ACTIVE,
                                "sortie_id": booking.sortie_id,
                            },
                        )
        elif event["type"] == "payment_intent.payment_failed":
            pi = event["data"]["object"]
            payment = Payment.objects.filter(stripe_payment_intent_id=pi["id"]).first()
            if payment:
                payment.status = Payment.Status.FAILED
                payment.save(update_fields=["status", "updated_at"])

                if payment.booking_id:
                    Booking.objects.filter(id=payment.booking_id).update(status=Booking.Status.CANCELLED)

        return Response({"received": True})
