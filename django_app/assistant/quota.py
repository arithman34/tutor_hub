"""Daily TutorHub AI question allowance.

Each account may ask `User.assistant_daily_limit` questions per UK calendar
day; a blank limit means unlimited. One question counts once, however many
model round trips it takes to answer. A question is reserved before the
model is called, so concurrent requests cannot both squeeze past the limit,
and handed back if the provider fails, so an outage does not use it up.
"""

from dataclasses import dataclass
from datetime import date, datetime

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import AssistantUsage
from .tools import LONDON


class QuotaExceeded(Exception):
    """The account has no questions left today."""


@dataclass(frozen=True)
class Allowance:
    limit: int | None
    used: int

    @property
    def unlimited(self) -> bool:
        return self.limit is None

    @property
    def remaining(self) -> int | None:
        return None if self.limit is None else max(self.limit - self.used, 0)

    @property
    def exhausted(self) -> bool:
        return self.limit is not None and self.used >= self.limit


def uk_today(now: datetime | None = None) -> date:
    return (now or timezone.now()).astimezone(LONDON).date()


def get_allowance(user, now: datetime | None = None) -> Allowance:
    usage = AssistantUsage.objects.filter(user=user, day=uk_today(now)).values_list("questions", flat=True).first()
    return Allowance(limit=user.assistant_daily_limit, used=usage or 0)


def reserve_question(user, now: datetime | None = None) -> date:
    """Count one question against today's allowance, or raise QuotaExceeded. Returns the day charged."""
    day = uk_today(now)
    with transaction.atomic():
        # Re-read the limit inside the transaction so an admin change applies immediately.
        limit = type(user).objects.values_list("assistant_daily_limit", flat=True).get(pk=user.pk)
        usage, _ = AssistantUsage.objects.select_for_update().get_or_create(user=user, day=day)
        if limit is not None and usage.questions >= limit:
            raise QuotaExceeded
        AssistantUsage.objects.filter(pk=usage.pk).update(questions=F("questions") + 1)
    return day


def refund_question(user, day: date) -> None:
    """Hand back a question reserved on `day` that could not be answered."""
    AssistantUsage.objects.filter(user=user, day=day, questions__gt=0).update(questions=F("questions") - 1)
