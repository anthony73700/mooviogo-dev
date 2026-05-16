"""Tests for AI services and view fallbacks.

These tests run with ``OPENAI_API_KEY=""`` so they exercise the deterministic
fallback path. Real OpenAI calls are never made in CI.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.ai.services import generate_event_brief, generate_social_post


@pytest.mark.django_db
def test_generate_social_post_fallback_friendly():
    payload = generate_social_post(event_title="Beach Party", city="Toulon", tone="friendly")
    assert payload["post"].startswith("Ce soir on sort ensemble.")
    assert "Beach Party" in payload["post"]
    assert "Toulon" in payload["post"]
    assert "#Mooviogo" in payload["hashtags"]


@pytest.mark.django_db
def test_generate_social_post_fallback_unknown_tone_defaults_to_friendly():
    payload = generate_social_post(event_title="Test", tone="wat")
    assert payload["post"].startswith("Ce soir on sort ensemble.")


@pytest.mark.django_db
def test_generate_event_brief_fallback_includes_audience():
    payload = generate_event_brief(city="Marseille", category="rooftop", audience="25-34")
    assert "Rooftop" in payload["title"]
    assert "Marseille" in payload["title"]
    assert "25-34" in payload["description"]
    assert "#rooftop" in payload["hashtags"]


@pytest.mark.django_db
def test_ai_create_post_endpoint_uses_service():
    User = get_user_model()
    user = User.objects.create_user(
        username="ai_user",
        email="ai@example.com",
        password="StrongPass123!",
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/api/v1/ai/create-post/",
        data={"event_title": "Sunset Party", "city": "Nice", "tone": "nightlife"},
        format="json",
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert "Sunset Party" in body["post"]
    assert "Nice" in body["post"]
    assert body["post"].startswith("La nuit commence maintenant.")
    assert "#Mooviogo" in body["hashtags"]


@pytest.mark.django_db
def test_ai_create_event_endpoint_uses_service():
    User = get_user_model()
    user = User.objects.create_user(
        username="ai_user2",
        email="ai2@example.com",
        password="StrongPass123!",
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/api/v1/ai/create-event/",
        data={"city": "Lyon", "category": "afterwork", "audience": "young pros"},
        format="json",
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert "Afterwork" in body["title"]
    assert "Lyon" in body["title"]
    assert "young pros" in body["description"]
