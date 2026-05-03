from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet

from .models import Booking
from .serializers import BookingCreateSerializer, BookingSerializer


class BookingViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return BookingCreateSerializer
        return BookingSerializer
