from django.urls import path

from .views import RevenueReportView

urlpatterns = [
    path("revenue/", RevenueReportView.as_view(), name="report-revenue"),
]
