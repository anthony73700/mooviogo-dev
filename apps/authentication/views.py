import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from apps.authentication.phone_verification import (
    clear_phone_otp_backoff,
    consume_phone_verification_token,
    create_phone_otp,
    get_phone_otp_block_remaining,
    increment_otp_alert_metric,
    verify_phone_otp,
)
from apps.authentication.serializers import (
    PhoneOTPRequestSerializer,
    PhoneOTPVerifySerializer,
    RegisterWithPhoneSerializer,
    SocialLoginSerializer,
)
from apps.authentication.social import SocialAuthError, get_social_profile
from apps.notifications.tasks import send_notification_task
from mooviogo.observability import emit_alert

User = get_user_model()


class RequestPhoneOTPThrottle(UserRateThrottle):
    scope = "otp_request"


class VerifyPhoneOTPThrottle(UserRateThrottle):
    scope = "otp_verify"


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterWithPhoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        phone_token = serializer.validated_data["phone_verification_token"]
        if not consume_phone_verification_token(phone, phone_token):
            return Response(
                {"phone_verification_token": ["Token OTP invalide ou deja consomme."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save(phone_verified_at=timezone.now())
        return Response(
            {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "display_name": user.display_name,
                "birth_date": user.birth_date,
                "phone": user.phone,
                "phone_verified": bool(user.phone_verified_at),
            },
            status=status.HTTP_201_CREATED,
        )


class RequestPhoneOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RequestPhoneOTPThrottle]

    def post(self, request):
        serializer = PhoneOTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        blocked_for = get_phone_otp_block_remaining(phone)
        if blocked_for > 0:
            increment_otp_alert_metric()
            emit_alert(
                "auth.api.request_otp.blocked",
                request=request,
                severity="warning",
                phone=phone,
                blocked_seconds=blocked_for,
            )
            return Response(
                {"detail": "OTP temporairement bloque sur ce numero.", "blocked_seconds": blocked_for},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Rotate code and clear previous verify backoff when a fresh OTP is requested.
        clear_phone_otp_backoff(phone)

        code = create_phone_otp(phone)
        message = f"Ton code Mooviogo: {code}. Code valable 10 minutes."
        try:
            try:
                send_notification_task.delay(channel="sms", to=phone, message=message, subject="Mooviogo OTP")
            except Exception:
                send_notification_task.run(channel="sms", to=phone, message=message, subject="Mooviogo OTP")
        except Exception:
            # OTP is still generated and can be verified during local QA.
            pass

        payload = {"detail": "Code OTP envoye."}
        if settings.DEBUG:
            payload["debug_code"] = code
        return Response(payload, status=status.HTTP_200_OK)


class VerifyPhoneOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [VerifyPhoneOTPThrottle]

    def post(self, request):
        serializer = PhoneOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]

        blocked_for = get_phone_otp_block_remaining(phone)
        if blocked_for > 0:
            increment_otp_alert_metric()
            emit_alert(
                "auth.api.verify_otp.blocked",
                request=request,
                severity="warning",
                phone=phone,
                blocked_seconds=blocked_for,
            )
            return Response(
                {"detail": "OTP temporairement bloque sur ce numero.", "blocked_seconds": blocked_for},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        token = verify_phone_otp(phone, code)
        if not token:
            block_seconds = get_phone_otp_block_remaining(phone)
            if block_seconds > 0:
                emit_alert(
                    "auth.api.verify_otp.backoff",
                    request=request,
                    severity="warning",
                    phone=phone,
                    blocked_seconds=block_seconds,
                )
                return Response(
                    {
                        "detail": "Trop de codes invalides. Reessaie plus tard.",
                        "blocked_seconds": block_seconds,
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response({"detail": "Code OTP invalide ou expire."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Telephone verifie.",
                "phone": phone,
                "phone_verification_token": token,
            },
            status=status.HTTP_200_OK,
        )


class SocialLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            profile = get_social_profile(
                provider=data["provider"],
                access_token=data.get("access_token", ""),
                id_token=data.get("id_token", ""),
            )
        except SocialAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        email = profile["email"].lower().strip()
        user = User.objects.filter(email__iexact=email).first()

        created = False
        if not user:
            birth_date = data.get("birth_date")
            phone = (data.get("phone") or "").strip()
            phone_token = (data.get("phone_verification_token") or "").strip()

            if not birth_date:
                return Response({"detail": "birth_date requis pour creer le compte social."}, status=status.HTTP_400_BAD_REQUEST)
            if not phone or not phone_token:
                return Response(
                    {"detail": "phone et phone_verification_token requis pour creer le compte social."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not consume_phone_verification_token(phone, phone_token):
                return Response({"detail": "Token OTP invalide ou deja consomme."}, status=status.HTTP_400_BAD_REQUEST)

            username_base = email.split("@")[0][:25] or f"{data['provider']}_user"
            username = username_base
            idx = 1
            while User.objects.filter(username=username).exists():
                idx += 1
                username = f"{username_base}{idx}"

            user = User.objects.create_user(
                email=email,
                username=username,
                display_name=profile.get("display_name", "")[:80],
                birth_date=birth_date,
                phone=phone,
                phone_verified_at=timezone.now(),
                password=secrets.token_urlsafe(24),
            )
            created = True

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "created": created,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "display_name": user.display_name,
                    "phone": user.phone,
                    "phone_verified": bool(user.phone_verified_at),
                },
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # JWT is stateless in this project. Client should delete access/refresh tokens.
        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


class VerifyView(TokenVerifyView):
    permission_classes = [permissions.AllowAny]
