from django.utils import timezone
from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet

from .models import SponsoredEvent
from .serializers import SponsoredEventSerializer


class SponsoredEventViewSet(ModelViewSet):
    serializer_class = SponsoredEventSerializer

    def get_queryset(self):
        queryset = SponsoredEvent.objects.all().order_by("-created_at")
        city = self.request.query_params.get("city", "").strip()
        active_only = self.request.query_params.get("active", "") == "1"

        if city:
            queryset = queryset.filter(city__icontains=city)
        if active_only:
            now = timezone.now()
            queryset = queryset.filter(status=SponsoredEvent.Status.ACTIVE, starts_at__lte=now, ends_at__gte=now)
        return queryset

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]
