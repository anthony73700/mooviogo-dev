from rest_framework.routers import DefaultRouter

from .views import SortieViewSet

router = DefaultRouter()
router.register("", SortieViewSet, basename="sortie")

urlpatterns = router.urls
