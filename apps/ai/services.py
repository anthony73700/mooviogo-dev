"""OpenAI-backed AI services with deterministic fallback.

All functions degrade gracefully when ``OPENAI_API_KEY`` is empty or when the
API call fails. This keeps tests deterministic in CI / dev environments while
allowing real generative output in production.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

_TONE_OPENINGS = {
    "friendly": "Ce soir on sort ensemble.",
    "premium": "Une soiree haut de gamme t'attend.",
    "nightlife": "La nuit commence maintenant.",
}


def _openai_available() -> bool:
    return bool(getattr(settings, "OPENAI_API_KEY", ""))


def _call_openai_json(prompt: str, *, system: str) -> dict[str, Any] | None:
    """Call OpenAI Chat Completions in JSON mode. Returns ``None`` on failure."""
    if not _openai_available():
        return None
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=getattr(settings, "OPENAI_TIMEOUT_SECONDS", 20),
        )
        completion = client.chat.completions.create(
            model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
        )
        raw = completion.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001 — broad catch keeps fallback safe
        logger.warning("openai_call_failed", extra={"error": str(exc)})
        return None


# ─── Social post generation ───────────────────────────────────────────────────


def generate_social_post(*, event_title: str, city: str = "", tone: str = "friendly") -> dict[str, Any]:
    tone = tone if tone in _TONE_OPENINGS else "friendly"

    prompt = (
        f"Genere un court post de promotion en francais pour un evenement local. "
        f"Ton: {tone}. Titre: '{event_title}'."
        + (f" Ville: {city}." if city else "")
        + " Reponds en JSON strict avec les cles 'post' (max 280 caracteres) et "
        "'hashtags' (liste de 4 hashtags pertinents commencant par #)."
    )
    system = (
        "Tu es un copywriter pour Mooviogo, une plateforme de sorties locales. "
        "Tes posts sont concis, en francais, et incitent au passage a l'action."
    )

    result = _call_openai_json(prompt, system=system)
    if result and isinstance(result.get("post"), str) and isinstance(result.get("hashtags"), list):
        return {
            "post": result["post"][:600],
            "hashtags": [str(h)[:40] for h in result["hashtags"][:6]],
        }

    # Deterministic fallback
    text = (
        f"{_TONE_OPENINGS[tone]} {event_title}"
        + (f" a {city}" if city else "")
        + ". Reserve ta place sur Mooviogo et invite ton crew."
    )
    return {
        "post": text,
        "hashtags": ["#Mooviogo", "#SortirCeSoir", "#EvenementLocal", "#Nightlife"],
    }


# ─── Event description generation ─────────────────────────────────────────────


def generate_event_brief(*, city: str, category: str, audience: str = "") -> dict[str, Any]:
    prompt = (
        f"Cree un brief d'evenement en francais pour la categorie '{category}' "
        f"a {city}."
        + (f" Audience cible: {audience}." if audience else "")
        + " Reponds en JSON strict avec les cles 'title' (max 80 caracteres), "
        "'description' (2-3 phrases, 280 caracteres max) et 'hashtags' (liste de 4)."
    )
    system = (
        "Tu es un assistant editorial pour Mooviogo. Tu rediges en francais, ton chaleureux, "
        "concret, mobile-first. Pas d'emojis."
    )

    result = _call_openai_json(prompt, system=system)
    if (
        result
        and isinstance(result.get("title"), str)
        and isinstance(result.get("description"), str)
        and isinstance(result.get("hashtags"), list)
    ):
        return {
            "title": result["title"][:160],
            "description": result["description"][:600],
            "hashtags": [str(h)[:40] for h in result["hashtags"][:6]],
        }

    # Deterministic fallback
    title = f"{category.title()} Experience - {city.title()}"
    description = (
        f"Un evenement {category} pense pour la communaute locale a {city}. "
        "Places limitees, ambiance conviviale et reservation instantanee."
    )
    if audience:
        description += f" Cible principale: {audience}."
    return {
        "title": title,
        "description": description,
        "hashtags": ["#Mooviogo", f"#{category.replace(' ', '')}", "#SortieLocale"],
    }
