from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.throttling import UserRateThrottle
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.events.models import Event
from apps.partners.models import Partner
from apps.sorties.models import Sortie
from mooviogo.observability import alert_on_threshold, emit_alert, emit_event

from .models import Ticket, TicketScanAudit
from .serializers import (
    TicketCreateSerializer,
    TicketScanAuditSerializer,
    TicketSerializer,
    TicketValidateSerializer,
)


class TicketValidateThrottle(UserRateThrottle):
    scope = "ticket_validate"


class TicketScanAuditsThrottle(UserRateThrottle):
    scope = "ticket_scan_audits"


class TicketViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Ticket.objects.filter(user=self.request.user).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return TicketCreateSerializer
        return TicketSerializer

    def _resolve_ticket_city(self, ticket):
        if ticket.sortie_id:
            sortie = Sortie.objects.filter(id=ticket.sortie_id).only("city").first()
            return (sortie.city if sortie and sortie.city else "")
        if ticket.event_id:
            event = Event.objects.filter(id=ticket.event_id).only("city").first()
            return (event.city if event and event.city else "")
        return ""

    def _operator_city(self, user):
        if user.is_staff:
            return ""
        partner = Partner.objects.filter(owner=user, status=Partner.Status.ACTIVE).only("city").first()
        if partner and partner.city:
            return partner.city
        return user.city or ""

    def _operator_partner(self, user):
        if user.is_staff:
            return None
        return Partner.objects.filter(owner=user, status=Partner.Status.ACTIVE).only("id", "city").first()

    def _is_operator_allowed_for_ticket(self, user, ticket):
        if user.is_staff:
            return True, ""
        if not user.is_partner:
            return False, "not_operator"

        partner = self._operator_partner(user)
        if not partner:
            return False, "inactive_partner"

        if ticket.event_id:
            event = Event.objects.filter(id=ticket.event_id).only("partner_id").first()
            if not event:
                return False, "event_not_found"
            if not event.partner_id:
                return False, "event_without_partner"
            return (event.partner_id == partner.id, "event_partner_mismatch" if event.partner_id != partner.id else "")

        if ticket.sortie_id:
            sortie = Sortie.objects.filter(id=ticket.sortie_id).only("type", "creator_id").first()
            if not sortie:
                return False, "sortie_not_found"
            if sortie.type == Sortie.Type.PARTENAIRE:
                if not sortie.creator_id:
                    return False, "sortie_without_owner"
                return (sortie.creator_id == user.id, "sortie_owner_mismatch" if sortie.creator_id != user.id else "")
            return False, "sortie_not_partner"

        return False, "ticket_missing_target"

    def _create_audit(self, *, request, ticket, token, outcome, reason_code, source, notes):
        TicketScanAudit.objects.create(
            ticket=ticket,
            operator=request.user,
            scanned_token=(token or "")[:80],
            outcome=outcome,
            reason_code=reason_code,
            source=source,
            operator_city=self._operator_city(request.user),
            target_city=self._resolve_ticket_city(ticket) if ticket else "",
            notes=notes or "",
        )

    @action(detail=False, methods=["post"], url_path="validate", throttle_classes=[TicketValidateThrottle])
    def validate_ticket(self, request):
        serializer = TicketValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["qr_token"].strip()
        source = serializer.validated_data.get("source") or TicketScanAudit.Source.API
        notes = serializer.validated_data.get("notes") or ""

        if not (request.user.is_staff or request.user.is_partner):
            emit_alert("tickets.api.validate.unauthorized_operator", request=request, severity="warning")
            return Response({"detail": "Acces reserve aux operateurs."}, status=status.HTTP_403_FORBIDDEN)

        if not token:
            self._create_audit(
                request=request,
                ticket=None,
                token=token,
                outcome=TicketScanAudit.Outcome.MISSING_TOKEN,
                reason_code="missing_token",
                source=source,
                notes=notes,
            )
            emit_event("tickets.api.validate.missing_token", request=request)
            return Response({"detail": "Token manquant.", "reason_code": "missing_token"}, status=status.HTTP_400_BAD_REQUEST)

        ticket = Ticket.objects.filter(qr_token=token).first()
        if not ticket:
            failures = alert_on_threshold(
                f"tickets:api:not_found:{request.user.id}",
                threshold=10,
                window_seconds=300,
                alert_name="tickets.api.high_not_found_rate",
                request=request,
                severity="warning",
            )
            self._create_audit(
                request=request,
                ticket=None,
                token=token,
                outcome=TicketScanAudit.Outcome.NOT_FOUND,
                reason_code="ticket_not_found",
                source=source,
                notes=notes,
            )
            emit_event("tickets.api.validate.not_found", request=request, failures_5m=failures)
            return Response({"detail": "Ticket introuvable.", "reason_code": "ticket_not_found"}, status=status.HTTP_404_NOT_FOUND)

        allowed, reason = self._is_operator_allowed_for_ticket(request.user, ticket)
        if not allowed:
            failures = alert_on_threshold(
                f"tickets:api:forbidden_scope:{request.user.id}",
                threshold=8,
                window_seconds=300,
                alert_name="tickets.api.high_forbidden_scope_rate",
                request=request,
                severity="warning",
                reason=reason,
            )
            self._create_audit(
                request=request,
                ticket=ticket,
                token=token,
                outcome=TicketScanAudit.Outcome.FORBIDDEN_SCOPE,
                reason_code=reason,
                source=source,
                notes=notes,
            )
            emit_event("tickets.api.validate.forbidden_scope", request=request, reason_code=reason, failures_5m=failures)
            return Response(
                {"detail": "Ce ticket n'est pas dans votre perimetre.", "reason_code": reason},
                status=status.HTTP_403_FORBIDDEN,
            )

        if ticket.status != Ticket.Status.ACTIVE:
            self._create_audit(
                request=request,
                ticket=ticket,
                token=token,
                outcome=TicketScanAudit.Outcome.INVALID_STATUS,
                reason_code=f"status_{ticket.status.lower()}",
                source=source,
                notes=notes,
            )
            emit_event("tickets.api.validate.invalid_status", request=request, reason_code=f"status_{ticket.status.lower()}")
            return Response(
                {"detail": "Ticket non valide.", "reason_code": f"status_{ticket.status.lower()}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ticket.status = Ticket.Status.USED
        ticket.used_at = timezone.now()
        ticket.save(update_fields=["status", "used_at", "updated_at"])

        self._create_audit(
            request=request,
            ticket=ticket,
            token=token,
            outcome=TicketScanAudit.Outcome.SUCCESS,
            reason_code="ok",
            source=source,
            notes=notes,
        )
        emit_event("tickets.api.validate.success", request=request, ticket_id=ticket.id, target_city=self._resolve_ticket_city(ticket))

        return Response(
            {
                "detail": "Ticket valide.",
                "ticket_id": ticket.id,
                "ticket_status": ticket.status,
                "used_at": ticket.used_at,
                "target_city": self._resolve_ticket_city(ticket),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="scan-audits", throttle_classes=[TicketScanAuditsThrottle])
    def scan_audits(self, request):
        if not (request.user.is_staff or request.user.is_partner):
            return Response({"detail": "Acces reserve aux operateurs."}, status=status.HTTP_403_FORBIDDEN)

        queryset = TicketScanAudit.objects.select_related("operator", "ticket").all()
        if not request.user.is_staff:
            queryset = queryset.filter(operator=request.user)

        try:
            limit = int(request.query_params.get("limit", 50) or 50)
        except (TypeError, ValueError):
            limit = 50
        limit = min(max(limit, 1), 200)
        serializer = TicketScanAuditSerializer(queryset[:limit], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
