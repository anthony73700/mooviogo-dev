from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.services import generate_event_brief, generate_social_post
from apps.events.models import Event
from apps.sorties.models import Sortie


class RecommendationInputSerializer(serializers.Serializer):
    city = serializers.CharField(required=False, allow_blank=True, max_length=100)
    interests = serializers.ListField(child=serializers.CharField(max_length=40), required=False)


class CreatePostInputSerializer(serializers.Serializer):
    city = serializers.CharField(required=False, allow_blank=True, max_length=100)
    tone = serializers.ChoiceField(choices=["friendly", "premium", "nightlife"], default="friendly")
    event_title = serializers.CharField(max_length=160)


class CreateEventInputSerializer(serializers.Serializer):
    city = serializers.CharField(max_length=100)
    category = serializers.CharField(max_length=80)
    audience = serializers.CharField(max_length=80, required=False, allow_blank=True)


class AIRecommendationsView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RecommendationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        city = serializer.validated_data.get("city", "")

        sorties = Sortie.objects.filter(status=Sortie.Status.OPEN).order_by("-created_at")
        events = Event.objects.filter(status=Event.Status.PUBLISHED).order_by("starts_at")

        if city:
            sorties = sorties.filter(city__icontains=city)
            events = events.filter(city__icontains=city)

        return Response(
            {
                "recommended_sorties": [
                    {"id": s.id, "title": s.title, "city": s.city, "is_free": s.is_free}
                    for s in sorties[:6]
                ],
                "recommended_events": [
                    {"id": e.id, "title": e.title, "city": e.city}
                    for e in events[:6]
                ],
            }
        )


class AICreatePostView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreatePostInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payload = generate_social_post(
            event_title=data["event_title"],
            city=data.get("city", "") or "",
            tone=data["tone"],
        )
        return Response(payload, status=status.HTTP_200_OK)


class AICreateEventView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreateEventInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payload = generate_event_brief(
            city=data["city"],
            category=data["category"],
            audience=data.get("audience", "") or "",
        )
        return Response(payload, status=status.HTTP_200_OK)
