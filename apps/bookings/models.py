from django.conf import settings
from django.db import models


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        CONFIRMED = "CONFIRMED", "Confirmée"
        CANCELLED = "CANCELLED", "Annulée"
        REFUNDED = "REFUNDED", "Remboursée"

    class BookingType(models.TextChoices):
        SORTIE = "SORTIE", "Sortie"
        RESTAURANT = "RESTAURANT", "Restaurant"
        ACTIVITY = "ACTIVITY", "Activité"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings")
    booking_type = models.CharField(max_length=20, choices=BookingType.choices)
    # Generic FK fields (sortie, restaurant slot, or activity session)
    sortie_id = models.PositiveIntegerField(null=True, blank=True)
    restaurant_slot_id = models.PositiveIntegerField(null=True, blank=True)
    activity_session_id = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    amount = models.PositiveIntegerField(default=0, help_text="Amount in cents.")
    currency = models.CharField(max_length=3, default="EUR")
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bookings_booking"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Booking {self.id} – {self.user} [{self.status}]"


class PartnerAgendaEntry(models.Model):
    class Source(models.TextChoices):
        MOOVIOGO = "MOOVIOGO", "Mooviogo"
        DIRECT = "DIRECT", "Direct"

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        CONFIRMED = "CONFIRMED", "Confirmée"
        CANCELLED = "CANCELLED", "Annulée"

    class ReservationKind(models.TextChoices):
        RESTAURANT = "RESTAURANT", "Restaurant"
        NIGHTLIFE = "NIGHTLIFE", "Nightlife"
        ACTIVITY = "ACTIVITY", "Activité"
        OTHER = "OTHER", "Autre"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="partner_agenda_entries",
    )
    partner = models.ForeignKey(
        "partners.Partner",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agenda_entries",
    )
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.DIRECT)
    reservation_kind = models.CharField(max_length=20, choices=ReservationKind.choices, default=ReservationKind.OTHER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    title = models.CharField(max_length=180)
    customer_name = models.CharField(max_length=120, blank=True)
    customer_contact = models.CharField(max_length=120, blank=True)
    party_size = models.PositiveIntegerField(null=True, blank=True)
    starts_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    linked_sortie = models.ForeignKey(
        "sorties.Sortie",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="partner_agenda_entries",
    )
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_partner_agenda_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bookings_partner_agenda_entry"
        ordering = ["starts_at", "-created_at"]

    def __str__(self) -> str:
        return f"Agenda {self.id} - {self.title} ({self.get_status_display()})"
