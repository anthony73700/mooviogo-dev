import json
import urllib.error
import urllib.request

import jwt
from django.conf import settings


class SocialAuthError(Exception):
    pass


def _http_get_json(url: str, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SocialAuthError("Impossible de recuperer les informations du fournisseur OAuth.") from exc


def get_google_profile(access_token: str) -> dict:
    payload = _http_get_json(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not payload.get("sub") or not payload.get("email"):
        raise SocialAuthError("Profil Google incomplet.")
    return {
        "external_id": payload["sub"],
        "email": payload["email"],
        "display_name": payload.get("name") or "",
    }


def get_facebook_profile(access_token: str) -> dict:
    payload = _http_get_json(
        f"https://graph.facebook.com/me?fields=id,name,email&access_token={access_token}"
    )
    if not payload.get("id") or not payload.get("email"):
        raise SocialAuthError("Profil Facebook incomplet (email requis).")
    return {
        "external_id": payload["id"],
        "email": payload["email"],
        "display_name": payload.get("name") or "",
    }


def get_apple_profile(id_token: str) -> dict:
    if not settings.APPLE_CLIENT_ID:
        raise SocialAuthError("APPLE_CLIENT_ID non configure pour OAuth Apple.")

    try:
        jwk_client = jwt.PyJWKClient(settings.APPLE_JWKS_URL)
        signing_key = jwk_client.get_signing_key_from_jwt(id_token)
        payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.APPLE_CLIENT_ID,
            issuer="https://appleid.apple.com",
        )
    except Exception as exc:
        raise SocialAuthError("id_token Apple invalide.") from exc

    if not payload.get("sub") or not payload.get("email"):
        raise SocialAuthError("Profil Apple incomplet (email requis).")

    return {
        "external_id": payload["sub"],
        "email": payload["email"],
        "display_name": payload.get("name") or payload.get("email", "").split("@")[0],
    }


def get_social_profile(provider: str, access_token: str, id_token: str) -> dict:
    if provider == "google":
        if not access_token:
            raise SocialAuthError("access_token requis pour Google.")
        return get_google_profile(access_token)
    if provider == "facebook":
        if not access_token:
            raise SocialAuthError("access_token requis pour Facebook.")
        return get_facebook_profile(access_token)
    if provider == "apple":
        if not id_token:
            raise SocialAuthError("id_token requis pour Apple.")
        return get_apple_profile(id_token)
    raise SocialAuthError("Provider OAuth non supporte.")
