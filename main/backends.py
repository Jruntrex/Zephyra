from main.models import User


class DemoBackend:
    """
    Authentication backend exclusively for demo sessions.
    Always reads from the isolated demo.db, regardless of the DB router state.
    This guarantees that demo users are never accidentally loaded from MySQL.
    """

    def authenticate(self, request, **kwargs):
        return None  # login() bypasses authenticate(); this backend only handles get_user

    def get_user(self, user_id):
        try:
            return User.objects.using("demo").get(pk=user_id)
        except User.DoesNotExist:
            return None
