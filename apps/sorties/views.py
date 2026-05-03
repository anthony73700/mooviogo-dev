from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Sortie, SortieParticipant
from .serializers import (
    SortieCreateSerializer,
    SortieDetailSerializer,
    SortieListSerializer,
    SortieParticipantSerializer,
)


class SortieViewSet(ModelViewSet):
    queryset = (
        Sortie.objects.annotate(participant_count=Count("participants"))
        .select_related("creator")
        .order_by("-created_at")
    )
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["city", "type", "status", "is_free"]
    search_fields = ["title", "description", "city"]
    ordering_fields = ["created_at", "starts_at", "participant_count"]

    def get_serializer_class(self):
        if self.action == "list":
            return SortieListSerializer
        if self.action in ("create", "update", "partial_update"):
            return SortieCreateSerializer
        return SortieDetailSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def join(self, request, pk=None):
        sortie = self.get_object()
        participant, created = SortieParticipant.objects.get_or_create(
            sortie=sortie,
            user=request.user,
            defaults={"status": SortieParticipant.ParticipationStatus.INTERESTED},
        )
        if not created and participant.status == SortieParticipant.ParticipationStatus.CANCELLED:
            participant.status = SortieParticipant.ParticipationStatus.INTERESTED
            participant.save()
        return Response(SortieParticipantSerializer(participant).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def leave(self, request, pk=None):
        sortie = self.get_object()
        SortieParticipant.objects.filter(sortie=sortie, user=request.user).update(
            status=SortieParticipant.ParticipationStatus.CANCELLED
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
