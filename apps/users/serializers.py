from rest_framework import serializers

from .models import User


class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "display_name", "avatar_url", "city", "is_verified"]
        read_only_fields = fields


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "display_name",
            "avatar_url",
            "bio",
            "city",
            "is_partner",
            "is_verified",
            "created_at",
        ]
        read_only_fields = ["id", "email", "is_partner", "is_verified", "created_at"]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "username", "display_name", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
