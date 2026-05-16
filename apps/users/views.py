from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError

from apps.authentication.phone_verification import consume_phone_verification_token
from .models import User
from .serializers import UserProfileSerializer, UserRegistrationSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        phone = serializer.validated_data["phone"]
        token = serializer.validated_data["phone_verification_token"]
        if not consume_phone_verification_token(phone, token):
            raise ValidationError({"phone_verification_token": "Token OTP invalide ou deja consomme."})
        serializer.save(phone_verified_at=timezone.now())


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
