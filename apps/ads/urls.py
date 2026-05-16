from rest_framework.routers import DefaultRouter

from .views import SponsoredEventViewSet

router = DefaultRouter()
router.register("", SponsoredEventViewSet, basename="sponsored-event")

urlpatterns = router.urls
