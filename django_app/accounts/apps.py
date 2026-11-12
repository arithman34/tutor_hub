from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        # Registers the OpenAPI description of CookieJWTAuthentication.
        from . import schema  # noqa: F401
