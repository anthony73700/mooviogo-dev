from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import permissions

from apps.sorties.models import Sortie
from apps.events.models import Event
from apps.public_events.models import PublicEvent
from apps.sorties.serializers import SortieListSerializer
from apps.events.serializers import EventListSerializer
from apps.public_events.serializers import PublicEventSerializer


class CityFeedView(APIView):
    """Aggregated city feed: sorties + events + public events for a given city."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        city = request.query_params.get("city", "")
        limit = min(int(request.query_params.get("limit", 10)), 50)

        sorties = Sortie.objects.filter(
            status=Sortie.Status.OPEN,
            city__icontains=city,
        ).order_by("-created_at")[:limit]

        events = Event.objects.filter(
            status=Event.Status.PUBLISHED,
            city__icontains=city,
        ).order_by("starts_at")[:limit]

        public_events = PublicEvent.objects.filter(
            status=PublicEvent.Status.ACTIVE,
            city__icontains=city,
        ).order_by("starts_at")[:limit]

        return Response({
            "sorties": SortieListSerializer(sorties, many=True).data,
            "events": EventListSerializer(events, many=True).data,
            "public_events": PublicEventSerializer(public_events, many=True).data,
        })
