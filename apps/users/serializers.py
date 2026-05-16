from datetime import date

from rest_framework import serializers

from apps.authentication.phone_verification import (
    is_phone_format_valid,
    is_phone_verification_token_valid,
    normalize_phone,
)
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
            "birth_date",
            "display_name",
            "avatar_url",
            "bio",
            "city",
            "phone",
            "phone_verified_at",
            "is_partner",
            "is_verified",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "email",
            "phone",
            "phone_verified_at",
            "is_partner",
            "is_verified",
            "created_at",
        ]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    birth_date = serializers.DateField()
    phone = serializers.CharField(max_length=20)
    phone_verification_token = serializers.CharField(write_only=True, max_length=64)

    class Meta:
        model = User
        fields = ["email", "username", "display_name", "birth_date", "phone", "phone_verification_token", "password"]

    def validate_birth_date(self, value):
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 18:
            raise serializers.ValidationError("Tu dois avoir au moins 18 ans pour creer un compte.")
        return value

    def validate_phone(self, value):
        phone = normalize_phone(value)
        if not is_phone_format_valid(phone):
            raise serializers.ValidationError("Numero de telephone invalide.")
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("Ce numero de telephone est deja utilise.")
        return phone

    def validate(self, attrs):
        if not is_phone_verification_token_valid(attrs["phone"], attrs["phone_verification_token"]):
            raise serializers.ValidationError({"phone_verification_token": "Token OTP invalide ou expire."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("phone_verification_token", None)
        return User.objects.create_user(**validated_data)
