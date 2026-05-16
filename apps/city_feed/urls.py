from django.urls import path

from .views import CityFeedView, GeocodeSearchView

urlpatterns = [
    path("", CityFeedView.as_view(), name="city-feed"),
    path("geocode/", GeocodeSearchView.as_view(), name="city-feed-geocode"),
]
