from django.db import models


class PublicEvent(models.Model):
    """External/aggregated public events (e.g. from OpenAgenda)."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Actif"
        EXPIRED = "EXPIRED", "Expiré"
        CANCELLED = "CANCELLED", "Annulé"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    source = models.CharField(max_length=50, default="openagenda", help_text="Data source identifier.")
    source_id = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    city = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    cover_image_url = models.URLField(blank=True)
    external_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    imported_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "public_events_event"
        ordering = ["starts_at"]

    def __str__(self) -> str:
        return f"{self.title} [{self.source}]"
