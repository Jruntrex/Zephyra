"""
Demo database router.

All 'main' app ORM queries are transparently redirected to the isolated
'demo' SQLite database when a demo session is active.
Django system tables (sessions, auth, contenttypes) always stay in the
default database so authentication and session handling work normally.

Activation: DemoModeMiddleware calls set_demo_mode(True) once it reads
is_demo=True from the session, using a thread-local so each request is
independent.
"""

import threading

_state = threading.local()


def set_demo_mode(active: bool) -> None:
    _state.active = active


def is_demo_active() -> bool:
    return getattr(_state, "active", False)


# Only 'main' app models go to the demo DB — system apps stay in default.
_DEMO_APP = "main"


class DemoDatabaseRouter:
    def _use_demo(self, model) -> bool:
        return is_demo_active() and model._meta.app_label == _DEMO_APP

    def db_for_read(self, model, **hints):
        return "demo" if self._use_demo(model) else None

    def db_for_write(self, model, **hints):
        return "demo" if self._use_demo(model) else None

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return True
