from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model for Mooviogo."""

    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=80, blank=True)
    avatar_url = models.URLField(blank=True)
    bio = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
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
