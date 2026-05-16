from django.urls import path

from .views import NotificationSendView, WebPushPublicKeyView, WebPushSubscriptionView

urlpatterns = [
    path("send/", NotificationSendView.as_view(), name="notifications-send"),
    path("web-push/public-key/", WebPushPublicKeyView.as_view(), name="notifications-web-push-public-key"),
    path("web-push/subscription/", WebPushSubscriptionView.as_view(), name="notifications-web-push-subscription"),
]
