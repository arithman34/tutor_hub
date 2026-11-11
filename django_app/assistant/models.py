from django.conf import settings
from django.db import models


class AssistantUsage(models.Model):
    """How many TutorHub AI questions an account has asked on one UK calendar day."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assistant_usage")
    day = models.DateField()
    questions = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "assistant_usage"
        constraints = [models.UniqueConstraint(fields=["user", "day"], name="assistant_usage_one_row_per_day")]

    def __str__(self):
        return f"{self.user} {self.day}: {self.questions}"
