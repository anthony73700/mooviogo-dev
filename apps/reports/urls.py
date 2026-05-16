from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReportViewSet, RevenueReportView

router = DefaultRouter()
router.register("", ReportViewSet, basename="report")

urlpatterns = [
    path("revenue/", RevenueReportView.as_view(), name="report-revenue"),
    path("", include(router.urls)),
]
