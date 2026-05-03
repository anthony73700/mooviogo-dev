from django.conf import settings
from django.db import models


class Sortie(models.Model):
    """Community outing (sortie communautaire)."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        OPEN = "OPEN", "Ouverte"
        FULL = "FULL", "Complète"
        CANCELLED = "CANCELLED", "Annulée"
        COMPLETED = "COMPLETED", "Terminée"

    class Type(models.TextChoices):
        COMMUNAUTAIRE = "COMMUNAUTAIRE", "Communautaire"
        PARTENAIRE = "PARTENAIRE", "Partenaire"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sorties",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    city = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.COMMUNAUTAIRE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    price = models.PositiveIntegerField(default=0, help_text="Price in cents. 0 = free.")
    currency = models.CharField(max_length=3, default="EUR")
    max_participants = models.PositiveIntegerField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    cover_image_url = models.URLField(blank=True)
    is_free = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sorties_sortie"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class SortieParticipant(models.Model):
    class ParticipationStatus(models.TextChoices):
        INTERESTED = "INTERESTED", "Intéressé"
        CONFIRMED = "CONFIRMED", "Confirmé"
        CANCELLED = "CANCELLED", "Annulé"

    sortie = models.ForeignKey(Sortie, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="participations")
    status = models.CharField(max_length=20, choices=ParticipationStatus.choices, default=ParticipationStatus.INTERESTED)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sorties_participant"
        unique_together = [["sortie", "user"]]

    def __str__(self) -> str:
        return f"{self.user} → {self.sortie}"
