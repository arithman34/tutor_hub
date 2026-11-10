from django.contrib import admin

from .models import GoogleCalendarToken


@admin.register(GoogleCalendarToken)
class GoogleCalendarTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "tutoring_calendar_id", "expires_at", "updated_at")
    readonly_fields = ("access_token", "refresh_token", "created_at", "updated_at")
    search_fields = ("user__email",)
