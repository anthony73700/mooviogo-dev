from django.urls import path

from .views import CityFeedView

urlpatterns = [
    path("", CityFeedView.as_view(), name="city-feed"),
]
