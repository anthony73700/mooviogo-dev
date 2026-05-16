from django.conf import settings
from rest_framework import serializers

from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    reporter_email = serializers.EmailField(source="reporter.email", read_only=True)
    reviewed_by_email = serializers.EmailField(source="reviewed_by.email", read_only=True)
    assigned_moderator_email = serializers.EmailField(source="assigned_moderator.email", read_only=True)
    evidence_file_url = serializers.SerializerMethodField()

    def get_evidence_file_url(self, obj):
        if obj.evidence_file:
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(obj.evidence_file.url)
            return obj.evidence_file.url
        return ""

    class Meta:
        model = Report
        fields = [
            "id",
            "reporter",
            "reporter_email",
            "target_type",
            "target_id",
            "category",
            "reason",
            "status",
            "evidence_url",
            "evidence_file",
            "evidence_file_url",
            "reviewed_by",
            "reviewed_by_email",
            "assigned_moderator",
            "assigned_moderator_email",
            "sla_due_at",
            "reviewed_at",
            "resolution_code",
            "suspension_ends_at",
            "moderation_notes",
            "decision_history",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reporter",
            "reviewed_by",
            "reviewed_at",
            "decision_history",
            "created_at",
            "updated_at",
        ]


class ReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ["target_type", "target_id", "category", "reason", "evidence_url", "evidence_file"]

    def validate_evidence_file(self, value):
        if not value:
            return value

        max_size = int(getattr(settings, "REPORT_EVIDENCE_MAX_SIZE_BYTES", 5 * 1024 * 1024))
        allowed_mime = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
        allowed_ext = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}

        if value.size > max_size:
            raise serializers.ValidationError("Fichier trop volumineux (max 5 Mo).")

        name = (value.name or "").lower()
        ext_ok = any(name.endswith(ext) for ext in allowed_ext)
        mime = (getattr(value, "content_type", "") or "").lower().strip()
        mime_ok = mime in allowed_mime if mime else False

        if not (ext_ok or mime_ok):
            raise serializers.ValidationError("Type de fichier non autorise (pdf, jpg, png, webp).")

        return value

    def create(self, validated_data):
        validated_data["reporter"] = self.context["request"].user
        return super().create(validated_data)
