from django.conf import settings
from django.db import models


class Partner(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        ACTIVE = "ACTIVE", "Actif"
        SUSPENDED = "SUSPENDED", "Suspendu"
        INACTIVE = "INACTIVE", "Inactif"

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="partner_profile",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    cover_image_url = models.URLField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "partners_partner"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.city})"
