from django.db import models


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        PUBLISHED = "PUBLISHED", "Publié"
        CANCELLED = "CANCELLED", "Annulé"
        COMPLETED = "COMPLETED", "Terminé"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    city = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    cover_image_url = models.URLField(blank=True)
    price = models.PositiveIntegerField(default=0, help_text="Price in cents. 0 = free.")
    currency = models.CharField(max_length=3, default="EUR")
    max_participants = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_partner_event = models.BooleanField(default=False)
    partner_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "events_event"
        ordering = ["starts_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.city})"
