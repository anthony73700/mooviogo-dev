from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    RefreshView,
    RegisterView,
    RequestPhoneOTPView,
    SocialLoginView,
    VerifyPhoneOTPView,
    VerifyView,
)

urlpatterns = [
    path("phone/request-otp/", RequestPhoneOTPView.as_view(), name="auth-phone-request-otp"),
    path("phone/verify-otp/", VerifyPhoneOTPView.as_view(), name="auth-phone-verify-otp"),
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("social-login/", SocialLoginView.as_view(), name="auth-social-login"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("verify/", VerifyView.as_view(), name="auth-verify"),
]
