import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
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


class GeocodeSearchView(APIView):
    """Geocoding endpoint for UX autocomplete/map pinning."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not settings.GEOCODING_ENABLED:
            return Response({"detail": "Geocoding desactive."}, status=503)

        query = (request.query_params.get("q") or "").strip()
        city = (request.query_params.get("city") or "").strip()
        if not query:
            return Response({"detail": "Parametre q requis."}, status=400)

        composed_query = query if not city else f"{query}, {city}"
        params = urllib.parse.urlencode(
            {
                "q": composed_query,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": 6,
            }
        )
        url = f"{settings.GEOCODING_NOMINATIM_URL}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": settings.GEOCODING_USER_AGENT})

        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError):
            return Response({"detail": "Erreur fournisseur geocoding."}, status=502)

        results = []
        for item in payload:
            lat = item.get("lat")
            lon = item.get("lon")
            if lat is None or lon is None:
                continue
            results.append(
                {
                    "display_name": item.get("display_name", ""),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "city": ((item.get("address") or {}).get("city") or (item.get("address") or {}).get("town") or ""),
                }
            )

        return Response({"results": results})
