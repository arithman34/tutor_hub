from django.conf import settings
from django.db import models


class GoogleCalendarToken(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True, related_name="google_calendar_token")
    access_token = models.CharField(max_length=2048)
    refresh_token = models.CharField(max_length=2048, null=True, blank=True)
    expires_at = models.DateTimeField()
    tutoring_calendar_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "google_calendar_tokens"

    def __str__(self):
        return f"Google Calendar token for {self.user_id}"

    @property
    def is_connected(self) -> bool:
        """A row alone doesn't mean connected — disconnect() leaves it behind."""
        return bool(self.refresh_token)
