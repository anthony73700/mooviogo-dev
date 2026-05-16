from django.conf import settings
from django.utils import translation


class UserPreferredLanguageMiddleware:
    """Apply authenticated user's saved language preference on each request."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.supported = {code for code, _ in settings.LANGUAGES}

    def __call__(self, request):
        preferred = ""
        if getattr(request, "user", None) and request.user.is_authenticated:
            preferred = (request.user.preferred_language or "").lower().split("-")[0]
            if preferred in self.supported and request.LANGUAGE_CODE != preferred:
                translation.activate(preferred)
                request.LANGUAGE_CODE = preferred

        response = self.get_response(request)

        if preferred and request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME) != preferred:
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, preferred)

        return response
