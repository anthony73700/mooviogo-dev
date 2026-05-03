from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import PublicEvent
from .serializers import PublicEventSerializer


class PublicEventViewSet(ReadOnlyModelViewSet):
    queryset = PublicEvent.objects.filter(status=PublicEvent.Status.ACTIVE)
    serializer_class = PublicEventSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["city", "source"]
    search_fields = ["title", "description", "city"]
    ordering_fields = ["starts_at", "imported_at"]
