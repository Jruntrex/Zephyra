from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.cache import add_never_cache_headers

from main.demo_router import set_demo_mode

# Paths where demo users are still allowed to POST (UI-only side effects)
_DEMO_WRITE_WHITELIST = (
    "/api/set-theme/",
    "/context/set/",
    "/logout/",
)


class DemoModeMiddleware:
    """
    - Activates the demo DB router (thread-local) for demo sessions so all
      'main' app ORM queries are transparently routed to demo.db.
    - Blocks write operations so the demo DB stays read-only from the UI.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_demo = bool(request.session.get("is_demo"))
        set_demo_mode(is_demo)
        try:
            if (
                is_demo
                and request.method in ("POST", "PUT", "PATCH", "DELETE")
                and not any(request.path.startswith(p) for p in _DEMO_WRITE_WHITELIST)
            ):
                if request.path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Демо-режим: зміни не дозволені."},
                        status=403,
                    )
                messages.warning(request, "Демо-режим: зміни не зберігаються.")
                return redirect(request.META.get("HTTP_REFERER", "/"))
            return self.get_response(request)
        finally:
            set_demo_mode(False)  # always clean up thread-local


class NoCacheAuthMiddleware:
    """
    Додає Cache-Control: no-store до всіх відповідей для авторизованих
    користувачів, щоб браузер не зберігав захищені сторінки в кеші.
    Після logout кнопка "Назад" не покаже стару сторінку.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Якщо юзер авторизований — забороняємо кешування відповіді
        if request.user.is_authenticated:
            add_never_cache_headers(response)

        return response
