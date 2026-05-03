from rest_framework.routers import DefaultRouter

from .views import RestaurantVenueViewSet

router = DefaultRouter()
router.register("", RestaurantVenueViewSet, basename="restaurant")

urlpatterns = router.urls
