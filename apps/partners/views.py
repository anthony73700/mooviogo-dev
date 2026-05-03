from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import Partner
from .serializers import PartnerDetailSerializer, PartnerListSerializer


class PartnerViewSet(ReadOnlyModelViewSet):
    queryset = Partner.objects.filter(status=Partner.Status.ACTIVE)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["city", "category", "is_verified"]
    search_fields = ["name", "description", "city"]
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PartnerDetailSerializer
        return PartnerListSerializer
