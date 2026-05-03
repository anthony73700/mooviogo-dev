from rest_framework import permissions
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import PartnerOpportunity
from .serializers import PartnerOpportunitySerializer


class PartnerOpportunityViewSet(ReadOnlyModelViewSet):
    queryset = PartnerOpportunity.objects.filter(status=PartnerOpportunity.Status.OPEN)
    serializer_class = PartnerOpportunitySerializer
    permission_classes = [permissions.AllowAny]
