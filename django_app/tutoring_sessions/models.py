import uuid

from django.conf import settings
from django.db import models


class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sessions")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="sessions")
    session_date = models.DateTimeField()
    session_start_time = models.DateTimeField()
    session_end_time = models.DateTimeField()
    zoom_meeting_uuid = models.CharField(max_length=255, null=True, blank=True)
    zoom_summary_raw = models.TextField(null=True, blank=True)
    work_covered = models.TextField(null=True, blank=True)
    student_actions = models.TextField(null=True, blank=True)
    tutor_actions = models.TextField(null=True, blank=True)
    next_lesson_focus = models.TextField(null=True, blank=True)
    topic_tags = models.CharField(max_length=255, null=True, blank=True)
    is_no_show = models.BooleanField(default=False)
    calendar_event_id = models.CharField(max_length=255, null=True, blank=True)
    calendar_recurring_id = models.CharField(max_length=255, null=True, blank=True)
    calendar_html_link = models.CharField(max_length=500, null=True, blank=True)
    ilp_generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sessions"
        ordering = ["-session_date"]
        indexes = [models.Index(fields=["user"])]

    def __str__(self):
        return f"{self.student} — {self.session_date:%Y-%m-%d}"

    @property
    def minutes(self):
        return int((self.session_end_time - self.session_start_time).total_seconds() / 60)
