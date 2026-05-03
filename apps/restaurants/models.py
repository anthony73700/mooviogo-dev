from django.db import models


class RestaurantVenue(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    city_slug = models.SlugField(max_length=100)
    city_label = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
    cover_image_url = models.URLField(blank=True)
    cuisine_type = models.CharField(max_length=100, blank=True)
    price_range = models.CharField(max_length=10, blank=True, help_text="€, €€, €€€")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "restaurants_venue"
        ordering = ["city_slug", "name"]
        unique_together = [["city_slug", "slug"]]

    def __str__(self) -> str:
        return f"{self.name} ({self.city_label})"


class RestaurantTimeSlot(models.Model):
    class SlotStatus(models.TextChoices):
        OPEN = "OPEN", "Disponible"
        FULL = "FULL", "Complet"
        CLOSED = "CLOSED", "Fermé"

    venue = models.ForeignKey(RestaurantVenue, on_delete=models.CASCADE, related_name="slots")
    date = models.DateField()
    time = models.TimeField()
    capacity = models.PositiveIntegerField(default=4)
    confirmed_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=SlotStatus.choices, default=SlotStatus.OPEN)

    class Meta:
        db_table = "restaurants_timeslot"
        ordering = ["date", "time"]
        unique_together = [["venue", "date", "time"]]

    def __str__(self) -> str:
        return f"{self.venue.name} – {self.date} {self.time}"
