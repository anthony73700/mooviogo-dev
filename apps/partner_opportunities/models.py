from django.db import models


class PartnerOpportunity(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Ouverte"
        CLOSED = "CLOSED", "Fermée"
        ARCHIVED = "ARCHIVED", "Archivée"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    city = models.CharField(max_length=100)
    category = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    partner_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "partner_opportunities_opportunity"
        ordering = ["-created_at"]
        verbose_name = "Partner opportunity"
        verbose_name_plural = "Partner opportunities"

    def __str__(self) -> str:
        return self.title
