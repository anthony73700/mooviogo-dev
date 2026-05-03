from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import RestaurantTimeSlot, RestaurantVenue
from .serializers import (
    RestaurantTimeSlotSerializer,
    RestaurantVenueDetailSerializer,
    RestaurantVenueListSerializer,
)


class RestaurantVenueViewSet(ReadOnlyModelViewSet):
    queryset = RestaurantVenue.objects.filter(is_active=True)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["city_slug", "cuisine_type"]
    search_fields = ["name", "city_label", "description"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return RestaurantVenueDetailSerializer
        return RestaurantVenueListSerializer

    @action(detail=True, methods=["get"], url_path="slots")
    def slots(self, request, pk=None):
        venue = self.get_object()
        date = request.query_params.get("date")
        qs = RestaurantTimeSlot.objects.filter(venue=venue, status=RestaurantTimeSlot.SlotStatus.OPEN)
        if date:
            qs = qs.filter(date=date)
        return Response(RestaurantTimeSlotSerializer(qs, many=True).data)
