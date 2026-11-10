import uuid

from django.conf import settings
from django.db import models


class Student(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="students")
    payee = models.ForeignKey("billing.Payee", on_delete=models.SET_NULL, null=True, blank=True, related_name="students")
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    level = models.CharField(max_length=100, null=True, blank=True)
    hourly_rate = models.FloatField(null=True, blank=True)
    zoom_meeting_id = models.CharField(max_length=255, null=True, blank=True)
    google_doc_id = models.CharField(max_length=255, null=True, blank=True)
    onedrive_shared_link = models.CharField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "students"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
