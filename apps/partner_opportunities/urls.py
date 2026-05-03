from rest_framework.routers import DefaultRouter

from .views import PartnerOpportunityViewSet

router = DefaultRouter()
router.register("", PartnerOpportunityViewSet, basename="partner-opportunity")

urlpatterns = router.urls
