from django.conf import settings
from django.db import models


class Report(models.Model):
    class Category(models.TextChoices):
        SPAM = "SPAM", "Spam"
        HARASSMENT = "HARASSMENT", "Harcelement"
        DANGEROUS = "DANGEROUS", "Comportement dangereux"
        SCAM = "SCAM", "Arnaque"
        OTHER = "OTHER", "Autre"

    class TargetType(models.TextChoices):
        USER = "USER", "Utilisateur"
        SORTIE = "SORTIE", "Sortie"
        EVENT = "EVENT", "Evenement"
        MESSAGE = "MESSAGE", "Message"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Ouvert"
        IN_REVIEW = "IN_REVIEW", "En cours"
        RESOLVED = "RESOLVED", "Traite"
        DISMISSED = "DISMISSED", "Rejete"

    class ResolutionCode(models.TextChoices):
        NONE = "NONE", "Aucune"
        RESOLVED_NO_ACTION = "RESOLVED_NO_ACTION", "Traite sans action"
        DISMISSED_NO_VIOLATION = "DISMISSED_NO_VIOLATION", "Rejete sans violation"
        USER_BANNED = "USER_BANNED", "Utilisateur banni"
        USER_TEMP_SUSPENDED = "USER_TEMP_SUSPENDED", "Utilisateur suspendu"
        CONTENT_REMOVED = "CONTENT_REMOVED", "Contenu retire"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_reports",
    )
    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    target_id = models.PositiveIntegerField()
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    evidence_url = models.URLField(blank=True)
    evidence_file = models.FileField(upload_to="reports/evidence/%Y/%m/%d", blank=True, null=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_reports",
    )
    assigned_moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_reports",
    )
    sla_due_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolution_code = models.CharField(max_length=40, choices=ResolutionCode.choices, default=ResolutionCode.NONE)
    suspension_ends_at = models.DateTimeField(null=True, blank=True)
    moderation_notes = models.TextField(blank=True)
    decision_history = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reports_report"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Report #{self.id} - {self.target_type}:{self.target_id}"
