from django.urls import path

from .views import (
    CreatePaymentIntentView,
    StripeConnectAccountView,
    StripeConnectOnboardingLinkView,
    StripeConnectStatusView,
    StripeWebhookView,
)

urlpatterns = [
    path("create-intent/", CreatePaymentIntentView.as_view(), name="payment-create-intent"),
    path("webhook/stripe/", StripeWebhookView.as_view(), name="payment-stripe-webhook"),
    path("connect/account/", StripeConnectAccountView.as_view(), name="payment-connect-account"),
    path("connect/onboarding-link/", StripeConnectOnboardingLinkView.as_view(), name="payment-connect-onboarding-link"),
    path("connect/status/", StripeConnectStatusView.as_view(), name="payment-connect-status"),
]
