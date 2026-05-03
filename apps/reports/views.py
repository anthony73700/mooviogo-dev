from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.sorties.models import Sortie


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
