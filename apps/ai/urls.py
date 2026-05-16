from django.urls import path

from .views import AICreateEventView, AICreatePostView, AIRecommendationsView

urlpatterns = [
    path("recommendations/", AIRecommendationsView.as_view(), name="ai-recommendations"),
    path("create-post/", AICreatePostView.as_view(), name="ai-create-post"),
    path("create-event/", AICreateEventView.as_view(), name="ai-create-event"),
]
