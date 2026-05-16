import uuid

from django.conf import settings
from django.db import models


class Ticket(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        ACTIVE = "ACTIVE", "Actif"
        USED = "USED", "Utilise"
        CANCELLED = "CANCELLED", "Annule"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets")
    booking_id = models.PositiveIntegerField(null=True, blank=True)
    event_id = models.PositiveIntegerField(null=True, blank=True)
    sortie_id = models.PositiveIntegerField(null=True, blank=True)
    qr_token = models.CharField(max_length=64, unique=True, editable=False)
    qr_payload = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tickets_ticket"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.qr_token:
            self.qr_token = uuid.uuid4().hex
        if not self.qr_payload:
            self.qr_payload = f"mooviogo:ticket:{self.qr_token}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Ticket {self.id} [{self.status}]"


class TicketScanAudit(models.Model):
    class Outcome(models.TextChoices):
        SUCCESS = "SUCCESS", "Succes"
        NOT_FOUND = "NOT_FOUND", "Ticket introuvable"
        INVALID_STATUS = "INVALID_STATUS", "Ticket invalide"
        FORBIDDEN_SCOPE = "FORBIDDEN_SCOPE", "Hors perimetre operateur"
        MISSING_TOKEN = "MISSING_TOKEN", "Token manquant"

    class Source(models.TextChoices):
        WEB = "WEB", "Interface web"
        API = "API", "API"

    ticket = models.ForeignKey(Ticket, null=True, blank=True, on_delete=models.SET_NULL, related_name="scan_audits")
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ticket_scan_audits")
    scanned_token = models.CharField(max_length=80, blank=True)
    outcome = models.CharField(max_length=24, choices=Outcome.choices)
    reason_code = models.CharField(max_length=60, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.WEB)
    operator_city = models.CharField(max_length=100, blank=True)
    target_city = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tickets_scan_audit"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Scan {self.id} {self.outcome}"
