from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model for Mooviogo."""

    class PreferredLanguage(models.TextChoices):
        FRENCH = "fr", "Francais"
        ENGLISH = "en", "English"
        SPANISH = "es", "Espanol"

    email = models.EmailField(unique=True)
    birth_date = models.DateField(null=True, blank=True)
    display_name = models.CharField(max_length=80, blank=True)
    avatar_url = models.URLField(blank=True)
    bio = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    preferred_language = models.CharField(
        max_length=5,
        choices=PreferredLanguage.choices,
        blank=True,
        default="",
    )
    is_partner = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users_user"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email
