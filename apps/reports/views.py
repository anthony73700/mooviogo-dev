from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework import permissions, serializers, status
from rest_framework.decorators import action
from rest_framework.throttling import UserRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.bookings.models import Booking
from apps.events.models import Event
from apps.payments.models import Payment
from apps.sorties.models import Sortie
from mooviogo.observability import emit_alert, emit_event

from .models import Report
from .serializers import ReportCreateSerializer, ReportSerializer
from .services import send_report_moderation_notifications

User = get_user_model()


class ReportModerationThrottle(UserRateThrottle):
    scope = "report_moderation"


class RevenueReportSerializer(serializers.Serializer):
    total_bookings = serializers.IntegerField()
    confirmed_bookings = serializers.IntegerField()
    total_payments_eur = serializers.IntegerField()
    total_sorties = serializers.IntegerField()


class RevenueReportView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        data = {
            "total_bookings": Booking.objects.count(),
            "confirmed_bookings": Booking.objects.filter(status=Booking.Status.CONFIRMED).count(),
            "total_payments_eur": sum(
                p.amount
                for p in Payment.objects.filter(status=Payment.Status.SUCCEEDED, currency="EUR")
            ),
            "total_sorties": Sortie.objects.count(),
        }
        return Response(RevenueReportSerializer(data).data)


class ReportViewSet(ModelViewSet):
    queryset = Report.objects.all().order_by("-created_at")
    http_method_names = ["get", "post", "patch", "head", "options"]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in (
            "list",
            "retrieve",
            "partial_update",
            "update",
            "resolve",
            "dismiss",
            "assign",
            "moderate",
        ):
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = Report.objects.all().order_by("-created_at")
        status_param = (self.request.query_params.get("status") or "").strip()
        category_param = (self.request.query_params.get("category") or "").strip()
        assigned_param = (self.request.query_params.get("assigned_to") or "").strip()

        if status_param:
            queryset = queryset.filter(status=status_param)
        if category_param:
            queryset = queryset.filter(category=category_param)
        if assigned_param == "me" and self.request.user.is_authenticated:
            queryset = queryset.filter(assigned_moderator=self.request.user)
        elif assigned_param.isdigit():
            queryset = queryset.filter(assigned_moderator_id=int(assigned_param))

        return queryset

    def _append_history(self, report, action_name, actor, details):
        history = list(report.decision_history or [])
        history.append(
            {
                "at": timezone.now().isoformat(),
                "actor_id": actor.id if actor else None,
                "actor_email": getattr(actor, "email", ""),
                "action": action_name,
                "details": details,
            }
        )
        report.decision_history = history

    def get_serializer_class(self):
        if self.action == "create":
            return ReportCreateSerializer
        return ReportSerializer

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)

    @action(detail=True, methods=["post"], url_path="resolve", throttle_classes=[ReportModerationThrottle])
    def resolve(self, request, pk=None):
        report = self.get_object()
        report.status = Report.Status.RESOLVED
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.resolution_code = Report.ResolutionCode.RESOLVED_NO_ACTION
        report.moderation_notes = (request.data.get("notes") or "").strip()
        self._append_history(report, "resolve", request.user, {"notes": report.moderation_notes})
        report.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "resolution_code",
                "moderation_notes",
                "decision_history",
                "updated_at",
            ]
        )
        send_report_moderation_notifications(report, request.user, "resolve")
        emit_event("reports.moderation.resolve", request=request, report_id=report.id)
        return Response({"detail": "Report resolved."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="dismiss", throttle_classes=[ReportModerationThrottle])
    def dismiss(self, request, pk=None):
        report = self.get_object()
        report.status = Report.Status.DISMISSED
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.resolution_code = Report.ResolutionCode.DISMISSED_NO_VIOLATION
        report.moderation_notes = (request.data.get("notes") or "").strip()
        self._append_history(report, "dismiss", request.user, {"notes": report.moderation_notes})
        report.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "resolution_code",
                "moderation_notes",
                "decision_history",
                "updated_at",
            ]
        )
        send_report_moderation_notifications(report, request.user, "dismiss")
        emit_event("reports.moderation.dismiss", request=request, report_id=report.id)
        return Response({"detail": "Report dismissed."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="assign", throttle_classes=[ReportModerationThrottle])
    def assign(self, request, pk=None):
        report = self.get_object()
        moderator_id = request.data.get("moderator_id")
        try:
            sla_hours = int(request.data.get("sla_hours") or 24)
        except (TypeError, ValueError):
            sla_hours = 24

        moderator = User.objects.filter(id=moderator_id, is_staff=True).first() if moderator_id else request.user
        if not moderator:
            return Response({"detail": "Moderateur introuvable."}, status=status.HTTP_400_BAD_REQUEST)

        report.assigned_moderator = moderator
        report.status = Report.Status.IN_REVIEW
        report.sla_due_at = timezone.now() + timedelta(hours=max(sla_hours, 1))
        self._append_history(
            report,
            "assign",
            request.user,
            {"assigned_to": moderator.id, "sla_hours": sla_hours},
        )
        report.save(update_fields=["assigned_moderator", "status", "sla_due_at", "decision_history", "updated_at"])
        send_report_moderation_notifications(report, request.user, "assign")
        emit_event(
            "reports.moderation.assign",
            request=request,
            report_id=report.id,
            assigned_moderator_id=moderator.id,
            sla_hours=sla_hours,
        )
        return Response({"detail": "Report assigne."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="moderate", throttle_classes=[ReportModerationThrottle])
    def moderate(self, request, pk=None):
        report = self.get_object()
        action_name = (request.data.get("action") or "").strip().lower()
        notes = (request.data.get("notes") or "").strip()
        try:
            suspension_days = int(request.data.get("suspension_days") or 7)
        except (TypeError, ValueError):
            suspension_days = 7

        resolution_code = Report.ResolutionCode.RESOLVED_NO_ACTION

        if action_name == "ban_user" and report.target_type == Report.TargetType.USER:
            user = User.objects.filter(id=report.target_id).first()
            if user:
                user.is_active = False
                user.save(update_fields=["is_active"])
            resolution_code = Report.ResolutionCode.USER_BANNED
        elif action_name == "temp_suspend_user" and report.target_type == Report.TargetType.USER:
            report.suspension_ends_at = timezone.now() + timedelta(days=max(suspension_days, 1))
            resolution_code = Report.ResolutionCode.USER_TEMP_SUSPENDED
        elif action_name == "remove_sortie" and report.target_type == Report.TargetType.SORTIE:
            Sortie.objects.filter(id=report.target_id).update(status=Sortie.Status.CANCELLED)
            resolution_code = Report.ResolutionCode.CONTENT_REMOVED
        elif action_name == "remove_event" and report.target_type == Report.TargetType.EVENT:
            Event.objects.filter(id=report.target_id).update(status=Event.Status.CANCELLED)
            resolution_code = Report.ResolutionCode.CONTENT_REMOVED

        report.status = Report.Status.RESOLVED
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.resolution_code = resolution_code
        report.moderation_notes = notes or f"Moderation action: {action_name}"
        self._append_history(
            report,
            "moderate",
            request.user,
            {
                "action": action_name,
                "notes": report.moderation_notes,
                "suspension_days": suspension_days if action_name == "temp_suspend_user" else 0,
            },
        )
        report.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "resolution_code",
                "suspension_ends_at",
                "moderation_notes",
                "decision_history",
                "updated_at",
            ]
        )
        send_report_moderation_notifications(report, request.user, f"moderate:{action_name}")
        emit_event("reports.moderation.moderate", request=request, report_id=report.id, action=action_name)
        if action_name == "ban_user":
            emit_alert(
                "reports.moderation.user_banned",
                request=request,
                severity="error",
                report_id=report.id,
                target_user_id=report.target_id,
            )
        if action_name == "temp_suspend_user":
            emit_alert(
                "reports.moderation.user_temp_suspended",
                request=request,
                severity="warning",
                report_id=report.id,
                target_user_id=report.target_id,
                suspension_days=suspension_days,
            )

        return Response({"detail": "Moderation action applied."}, status=status.HTTP_200_OK)
