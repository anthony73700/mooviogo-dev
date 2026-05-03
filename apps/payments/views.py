import stripe
from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment


class CreatePaymentIntentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        amount = request.data.get("amount")
        currency = request.data.get("currency", "eur")
        booking_id = request.data.get("booking_id")

        if not amount or not isinstance(amount, int) or amount <= 0:
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)

        stripe.api_key = settings.STRIPE_SECRET_KEY

        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
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
            Payment.objects.filter(stripe_payment_intent_id=pi["id"]).update(
                status=Payment.Status.SUCCEEDED,
                stripe_charge_id=pi.get("latest_charge", ""),
            )
        elif event["type"] == "payment_intent.payment_failed":
            pi = event["data"]["object"]
            Payment.objects.filter(stripe_payment_intent_id=pi["id"]).update(
                status=Payment.Status.FAILED,
            )

        return Response({"received": True})
