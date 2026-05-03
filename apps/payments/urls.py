from django.urls import path

from .views import CreatePaymentIntentView, StripeWebhookView

urlpatterns = [
    path("create-intent/", CreatePaymentIntentView.as_view(), name="payment-create-intent"),
    path("webhook/stripe/", StripeWebhookView.as_view(), name="payment-stripe-webhook"),
]
