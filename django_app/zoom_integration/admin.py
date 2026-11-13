from django.contrib import admin

from .models import ZoomMeetingEvent, ZoomToken


@admin.register(ZoomToken)
class ZoomTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "updated_at")
    # Live OAuth credentials: never render them, not even read-only.
    exclude = ("access_token", "refresh_token")
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("user__email",)


@admin.register(ZoomMeetingEvent)
class ZoomMeetingEventAdmin(admin.ModelAdmin):
    list_display = ("meeting_uuid", "student", "start_time", "source", "status", "attempts", "session", "created_at")
    list_filter = ("status", "source")
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("user__email", "meeting_id", "meeting_uuid")
