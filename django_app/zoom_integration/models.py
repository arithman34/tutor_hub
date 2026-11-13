from django.conf import settings
from django.db import models


class ZoomToken(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True, related_name="zoom_token")
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "zoom_tokens"

    def __str__(self):
        return f"Zoom token for {self.user_id}"


class ZoomMeetingEvent(models.Model):
    """One finished occurrence of a student's Zoom meeting, waiting to be (or
    already) logged as a Session. Created by the summary webhook or the
    catch-up sweep; meeting_uuid is unique, so a repeated delivery is a no-op."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    class Source(models.TextChoices):
        WEBHOOK = "webhook", "Webhook"
        SWEEP = "sweep", "Catch-up sweep"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="zoom_meeting_events")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="zoom_meeting_events")
    session = models.ForeignKey("tutoring_sessions.Session", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    meeting_id = models.CharField(max_length=32)
    meeting_uuid = models.CharField(max_length=255, unique=True)
    start_time = models.DateTimeField(null=True, blank=True, help_text="Real UTC, as Zoom reports it.")
    source = models.CharField(max_length=16, choices=Source.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "zoom_meeting_events"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self):
        return f"Zoom meeting {self.meeting_uuid} ({self.status})"
