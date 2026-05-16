from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.authentication.phone_verification import (
    is_phone_format_valid,
    is_phone_verification_token_valid,
    normalize_phone,
)

User = get_user_model()


class PhoneOTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value):
        phone = normalize_phone(value)
        if not is_phone_format_valid(phone):
            raise serializers.ValidationError("Numero de telephone invalide. Utilise le format international.")
        return phone


class PhoneOTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6, min_length=6)

    def validate_phone(self, value):
        phone = normalize_phone(value)
        if not is_phone_format_valid(phone):
            raise serializers.ValidationError("Numero de telephone invalide.")
        return phone


class RegisterWithPhoneSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    birth_date = serializers.DateField()
    phone = serializers.CharField(max_length=20)
    phone_verification_token = serializers.CharField(write_only=True, max_length=64)

    class Meta:
        model = User
        fields = [
            "email",
            "username",
            "display_name",
            "birth_date",
            "phone",
            "phone_verification_token",
            "password",
        ]

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


class SocialLoginSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["google", "facebook", "apple"])
    access_token = serializers.CharField(required=False, allow_blank=True)
    id_token = serializers.CharField(required=False, allow_blank=True)
    birth_date = serializers.DateField(required=False)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    phone_verification_token = serializers.CharField(required=False, allow_blank=True, max_length=64)

    def validate_phone(self, value):
        if not value:
            return ""
        phone = normalize_phone(value)
        if not is_phone_format_valid(phone):
            raise serializers.ValidationError("Numero de telephone invalide.")
        return phone
