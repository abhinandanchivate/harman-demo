from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
    verbose_name = "FHIR Patient Portal API"

    def ready(self) -> None:
        # Lazy import to avoid side effects during migrations
        from . import signals  # noqa: F401
