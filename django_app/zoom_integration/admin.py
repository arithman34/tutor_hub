from django.contrib import admin

from .models import ZoomToken


@admin.register(ZoomToken)
class ZoomTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "updated_at")
    # Live OAuth credentials: never render them, not even read-only.
    exclude = ("access_token", "refresh_token")
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("user__email",)
