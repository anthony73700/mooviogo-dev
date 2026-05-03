from django.conf import settings
from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        SUCCEEDED = "SUCCEEDED", "Réussi"
        FAILED = "FAILED", "Échoué"
        REFUNDED = "REFUNDED", "Remboursé"
        CANCELLED = "CANCELLED", "Annulé"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="payments")
    booking_id = models.PositiveIntegerField(null=True, blank=True)
    amount = models.PositiveIntegerField(help_text="Amount in cents.")
    currency = models.CharField(max_length=3, default="EUR")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    stripe_payment_intent_id = models.CharField(max_length=100, unique=True)
    stripe_charge_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments_payment"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Payment {self.stripe_payment_intent_id} [{self.status}]"
