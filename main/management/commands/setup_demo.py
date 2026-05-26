"""
Management command: setup_demo

Creates a shared demo admin user for guest demo mode.
Run once after deploying (or after reset_and_seed) to enable the /demo/ endpoint.

  python manage.py setup_demo

Demo login:
  email   : demo_admin@mentorly.app
  password: demo1234
  role    : admin  (read-only via DemoModeMiddleware)
"""

from django.core.management.base import BaseCommand

from main.models import User

DEMO_EMAIL = "demo_admin@mentorly.app"
DEMO_PASSWORD = "demo1234"


class Command(BaseCommand):
    help = "Creates (or resets) the demo admin user for /demo/ guest mode."

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            email=DEMO_EMAIL,
            defaults={
                "full_name": "Демо Адміністратор",
                "role": "admin",
                "is_staff": True,
                "is_active": True,
            },
        )
        user.full_name = "Демо Адміністратор"
        user.role = "admin"
        user.is_staff = True
        user.is_active = True
        user.set_password(DEMO_PASSWORD)
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action}: {DEMO_EMAIL} / {DEMO_PASSWORD}"))
        self.stdout.write(
            "Tip: run 'python manage.py reset_and_seed' first to populate demo data."
        )
