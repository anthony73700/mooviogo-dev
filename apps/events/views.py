from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions
from rest_framework.viewsets import ModelViewSet

from .models import Event
from .serializers import EventCreateSerializer, EventDetailSerializer, EventListSerializer


class EventViewSet(ModelViewSet):
    queryset = Event.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["city", "status", "is_partner_event"]
    search_fields = ["title", "description", "city"]
    ordering_fields = ["starts_at", "created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return EventListSerializer
        if self.action in ("create", "update", "partial_update"):
            return EventCreateSerializer
        return EventDetailSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
