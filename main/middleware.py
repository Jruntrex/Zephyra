from django.utils.cache import add_never_cache_headers


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
