from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.events.models import Event
from apps.partners.models import Partner
from apps.tickets.models import Ticket, TicketScanAudit

User = get_user_model()


class TicketValidationApiTests(APITestCase):
    def setUp(self):
        self.operator_user = User.objects.create_user(
            username="operator",
            email="operator@example.com",
            password="strong-pass-123",
            is_partner=True,
            city="Paris",
        )
        self.other_partner_owner = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="strong-pass-123",
            is_partner=True,
            city="Lyon",
        )
        self.customer = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="strong-pass-123",
            city="Paris",
        )

        self.operator_partner = Partner.objects.create(
            owner=self.operator_user,
            name="Partner A",
            slug="partner-a",
            city="Paris",
            status=Partner.Status.ACTIVE,
        )
        self.other_partner = Partner.objects.create(
            owner=self.other_partner_owner,
            name="Partner B",
            slug="partner-b",
            city="Lyon",
            status=Partner.Status.ACTIVE,
        )

        self.event_owned = Event.objects.create(
            title="Event owned",
            slug="event-owned",
            city="Paris",
            starts_at="2030-01-01T20:00:00Z",
            status=Event.Status.PUBLISHED,
            is_partner_event=True,
            partner_id=self.operator_partner.id,
        )
        self.event_other = Event.objects.create(
            title="Event other",
            slug="event-other",
            city="Lyon",
            starts_at="2030-01-02T20:00:00Z",
            status=Event.Status.PUBLISHED,
            is_partner_event=True,
            partner_id=self.other_partner.id,
        )

    def _validate_url(self):
        return "/api/v1/tickets/validate/"

    def test_operator_can_validate_ticket_for_owned_event(self):
        ticket = Ticket.objects.create(
            user=self.customer,
            event_id=self.event_owned.id,
            status=Ticket.Status.ACTIVE,
        )
        self.client.force_authenticate(self.operator_user)

        with patch("apps.tickets.views.emit_event") as mock_emit_event:
            response = self.client.post(self._validate_url(), {"qr_token": ticket.qr_token}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.USED)
        self.assertTrue(mock_emit_event.called)
        self.assertTrue(
            TicketScanAudit.objects.filter(
                ticket=ticket,
                operator=self.operator_user,
                outcome=TicketScanAudit.Outcome.SUCCESS,
            ).exists()
        )

    def test_operator_cannot_validate_ticket_for_other_partner_event(self):
        ticket = Ticket.objects.create(
            user=self.customer,
            event_id=self.event_other.id,
            status=Ticket.Status.ACTIVE,
        )
        self.client.force_authenticate(self.operator_user)

        response = self.client.post(self._validate_url(), {"qr_token": ticket.qr_token}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("reason_code"), "event_partner_mismatch")
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.ACTIVE)
        self.assertTrue(
            TicketScanAudit.objects.filter(
                ticket=ticket,
                operator=self.operator_user,
                outcome=TicketScanAudit.Outcome.FORBIDDEN_SCOPE,
                reason_code="event_partner_mismatch",
            ).exists()
        )
