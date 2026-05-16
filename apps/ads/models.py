from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SponsoredEvent(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "En pause"
        ENDED = "ENDED", "Terminee"

    city = models.CharField(max_length=100)
    event_id = models.PositiveIntegerField()
    slot_name = models.CharField(max_length=40, default="homepage")
    budget_eur = models.PositiveIntegerField(default=30)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ads_sponsored_event"
        ordering = ["-created_at"]

    def clean(self):
        if self.status != self.Status.ACTIVE:
            return

        qs = SponsoredEvent.objects.filter(city__iexact=self.city, status=self.Status.ACTIVE)
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        # Premium rule: max 3 active sponsored events per city.
        if qs.count() >= 3:
            raise ValidationError({"city": "Maximum 3 evenements sponsorises actifs par ville."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Sponsored #{self.event_id} - {self.city}"
