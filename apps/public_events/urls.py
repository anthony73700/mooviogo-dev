from rest_framework.routers import DefaultRouter

from .views import PublicEventViewSet

router = DefaultRouter()
router.register("", PublicEventViewSet, basename="public-event")

urlpatterns = router.urls
