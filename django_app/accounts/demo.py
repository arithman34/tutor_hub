"""The demo account: a shared, read-only login filled with made-up records.

The homepage's "Try the demo" button signs visitors into it (sign_in), so
anyone can look round TutorHub without an invitation. accounts/permissions.py
stops it changing anything, and its AI allowance is capped because every
visitor shares it.

Its records are generated relative to today: a year of weekly lessons for
nine students, the payments their parents made, and the odd no-show. Since
they'd otherwise go stale ("no lessons this week"), they're regenerated on
the first sign-in once they're a week old. Every name, email and phone
number is fictional (phone numbers are from Ofcom's range reserved for
drama, emails use example.com).
"""

import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_timezone

from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session

from .models import User

REFRESH_AFTER = timedelta(days=7)
DEFAULT_MONTHS = 12
DEFAULT_SEED = 42


class DemoUnavailable(Exception):
    """The demo is switched off, or its email belongs to a real account."""


@dataclass(frozen=True)
class DemoStudent:
    first_name: str
    payee: str  # Key into PAYEES
    level: str
    subject: str  # Key into TOPICS
    rate: float
    weekday: int  # 0 = Monday
    start: time
    minutes: int
    joined_months_ago: int
    left_months_ago: int | None = None  # None = still a student


# Parents (payees) and the children they pay for. Siblings share a payee.
PAYEES = {
    "harper": ("Claire", "Harper", "07700 900123", "HARPER TUITION"),
    "okafor": ("Daniel", "Okafor", "07700 900456", "OKAFOR"),
    "patel": ("Priya", "Patel", "07700 900789", "PATEL MATHS"),
    "whitfield": ("Sarah", "Whitfield", "07700 900321", "WHITFIELD"),
    "nowak": ("Marek", "Nowak", "07700 900654", "NOWAK A"),
    "bennett": ("Helen", "Bennett", "07700 900987", "BENNETT"),
}

STUDENTS = [
    DemoStudent("Ella", "harper", "GCSE", "maths", 35, 0, time(16, 0), 60, 12),
    DemoStudent("Jack", "harper", "KS3", "maths", 30, 0, time(17, 15), 60, 9),
    DemoStudent("Tobi", "okafor", "A-Level", "physics", 45, 1, time(17, 0), 90, 11),
    DemoStudent("Anika", "patel", "11+", "eleven_plus", 32, 2, time(16, 30), 60, 8),
    DemoStudent("Rohan", "patel", "GCSE", "physics", 38, 3, time(18, 0), 60, 5),
    DemoStudent("Grace", "whitfield", "A-Level", "maths", 45, 3, time(16, 0), 60, 12, left_months_ago=4),
    DemoStudent("Oliver", "nowak", "GCSE", "maths", 35, 4, time(16, 0), 60, 7),
    DemoStudent("Maya", "bennett", "KS3", "maths", 30, 1, time(16, 0), 60, 3),
    DemoStudent("Leo", "bennett", "GCSE", "physics", 35, 5, time(10, 0), 90, 10, left_months_ago=6),
]

# (work covered, topic tags) for each subject, used in rotation.
TOPICS = {
    "maths": [
        ("Solving quadratics by factorising and the quadratic formula", "algebra,quadratics"),
        ("Simultaneous equations, one linear and one quadratic", "algebra,simultaneous equations"),
        ("Sine and cosine rules, including bearings questions", "trigonometry"),
        ("Probability trees and conditional probability", "probability"),
        ("Circle theorems and writing up the reasoning", "geometry,circle theorems"),
        ("Rearranging formulae and changing the subject", "algebra"),
        ("Vectors: proving points are collinear", "vectors"),
        ("Differentiation: tangents and stationary points", "calculus"),
        ("Fractions, percentages and reverse percentages", "number"),
        ("Past paper practice under timed conditions", "exam practice"),
    ],
    "physics": [
        ("Forces and Newton's laws, resolving into components", "mechanics,forces"),
        ("Electric circuits: series, parallel and potential dividers", "electricity"),
        ("Waves, refraction and total internal reflection", "waves"),
        ("Specific heat capacity required practical", "thermal physics,practicals"),
        ("Momentum and conservation in collisions", "mechanics,momentum"),
        ("Radioactive decay and half-life calculations", "nuclear physics"),
        ("Projectile motion with SUVAT", "mechanics,kinematics"),
        ("Past paper practice: six-mark explanation questions", "exam practice"),
    ],
    "eleven_plus": [
        ("Verbal reasoning: codes and letter sequences", "verbal reasoning"),
        ("Non-verbal reasoning: rotations and reflections", "non-verbal reasoning"),
        ("Comprehension: inference questions", "english,comprehension"),
        ("Mental arithmetic speed drills and word problems", "maths,arithmetic"),
        ("Timed mixed practice paper", "exam practice"),
    ],
}

STUDENT_ACTIONS = [
    "Finish the practice sheet from today, questions 5 to 12.",
    "Redo the two questions we got stuck on without notes.",
    "Spend 20 minutes on the topic summary and make flashcards.",
    "Complete one timed past paper section before next lesson.",
    "Write up the method for the last example in your own words.",
]
TUTOR_ACTIONS = [
    "Prepare a mixed revision sheet on this topic.",
    "Find two harder exam-style questions to stretch further.",
    "Mark the homework and pick out common mistakes to go over.",
    "Send a short progress update to the parent.",
    "",
]
NEXT_FOCUS = [
    "Check homework, then move on to the next topic.",
    "Exam technique: reading the question and showing working.",
    "Consolidate today's topic with harder examples.",
    "Revisit anything still shaky from the last two lessons.",
]


def wall_clock(day, at: time) -> datetime:
    """The app stores lesson times as the local wall-clock time, marked UTC."""
    return datetime.combine(day, at, tzinfo=timezone.utc)


def months_ago(today, months: int):
    year, month = divmod(today.year * 12 + today.month - 1 - months, 12)
    return today.replace(year=year, month=month + 1, day=1)


def get_or_create_user() -> User:
    """The demo account, created on first use with no password (sign_in is the only way in)."""
    if not settings.DEMO_ENABLED:
        raise DemoUnavailable("The demo is switched off.")
    user = User.objects.filter(email=settings.DEMO_EMAIL).first()
    if user is None:
        user = User.objects.create_user(
            email=settings.DEMO_EMAIL,
            password=None,
            first_name="Alex",
            last_name="Morgan",
            address="12 Example Road, Leeds",
            is_demo=True,
        )
    elif not user.is_demo:
        raise DemoUnavailable(f"{settings.DEMO_EMAIL} is a real account, not the demo.")
    # Applied every time, so changing DEMO_AI_DAILY_LIMIT takes effect on the next sign-in.
    if user.assistant_daily_limit != settings.DEMO_AI_DAILY_LIMIT:
        user.assistant_daily_limit = settings.DEMO_AI_DAILY_LIMIT
        user.save(update_fields=["assistant_daily_limit", "updated_at"])
    return user


def sign_in() -> User:
    """The demo account for a visitor to be signed in as, its records refreshed if they've gone stale.

    Raises DemoUnavailable.
    """
    with transaction.atomic():
        user = get_or_create_user()
        # Lock the row so two visitors arriving together don't both regenerate the records.
        user = User.objects.select_for_update().get(pk=user.pk)
        if user.demo_seeded_at is None or django_timezone.now() - user.demo_seeded_at > REFRESH_AFTER:
            fill(user)
    return user


def fill(user: User, months: int = DEFAULT_MONTHS, seed: int = DEFAULT_SEED) -> dict[str, int]:
    """Replace the account's students, payees, sessions and payments with `months` of made-up ones.

    Same seed, same day: same records. Returns how many of each it made.
    """
    if not user.is_demo:
        raise ValueError("Only the demo account's records may be replaced.")
    rng = random.Random(seed)
    with transaction.atomic():
        for model in (Session, Payment, Student, Payee):
            model.objects.filter(user=user).delete()
        counts = _create_records(user, months, rng)
        user.demo_seeded_at = django_timezone.now()
        user.save(update_fields=["demo_seeded_at", "updated_at"])
    return counts


def _create_records(user, months, rng):
    now = datetime.now(timezone.utc)
    today = now.date()
    history_start = months_ago(today, months)

    payees = {
        key: Payee.objects.create(
            user=user,
            first_name=first,
            last_name=last,
            email=f"{first}.{last}@example.com".lower(),
            phone_number=phone,
            bank_reference_pattern=reference,
        )
        for key, (first, last, phone, reference) in PAYEES.items()
    }

    session_count = 0
    cost_by_payee_month: dict[tuple[str, tuple[int, int]], float] = {}
    for spec in STUDENTS:
        joined = max(months_ago(today, min(spec.joined_months_ago, months)), history_start)
        left = months_ago(today, spec.left_months_ago) if spec.left_months_ago is not None else None
        student = Student.objects.create(
            user=user,
            payee=payees[spec.payee],
            first_name=spec.first_name,
            last_name=payees[spec.payee].last_name,
            level=spec.level,
            hourly_rate=spec.rate,
            is_active=left is None,
        )
        # Analytics counts new students by when they were added, so backdate it.
        Student.objects.filter(pk=student.pk).update(created_at=wall_clock(joined, time(9, 0)))

        day = joined + timedelta(days=(spec.weekday - joined.weekday()) % 7)
        topics = TOPICS[spec.subject]
        lesson = 0
        sessions = []
        while day < today and (left is None or day < left):
            # Roughly two weeks off at Christmas and in August, plus the odd skipped week.
            holiday = (day.month == 12 and day.day >= 20) or (day.month == 1 and day.day <= 3) or (day.month == 8 and day.day <= 14)
            if not holiday and rng.random() > 0.06:
                start = wall_clock(day, spec.start)
                end = start + timedelta(minutes=spec.minutes)
                no_show = rng.random() < 0.04
                notes = {}
                # No notes for a no-show; a recent lesson may not be written up yet, as in real use.
                if not no_show and ((today - day).days > 10 or rng.random() < 0.5):
                    work, tags = topics[lesson % len(topics)]
                    notes = {
                        "work_covered": work,
                        "topic_tags": tags,
                        "student_actions": rng.choice(STUDENT_ACTIONS),
                        "tutor_actions": rng.choice(TUTOR_ACTIONS) or None,
                        "next_lesson_focus": rng.choice(NEXT_FOCUS),
                    }
                sessions.append(
                    Session(
                        user=user,
                        student=student,
                        session_date=start,
                        session_start_time=start,
                        session_end_time=end,
                        is_no_show=no_show,
                        **notes,
                    )
                )
                # No-shows are still charged, as the balances assume.
                key = (spec.payee, (day.year, day.month))
                cost_by_payee_month[key] = cost_by_payee_month.get(key, 0) + spec.minutes / 60 * spec.rate
                lesson += 1
            day += timedelta(days=7)
        Session.objects.bulk_create(sessions)
        session_count += len(sessions)

    # Each payee settles the month's lessons early the next month. The
    # current month isn't due yet, and one family is a month behind, so
    # the dashboard and payees list have balances outstanding to show.
    payments = []
    late_payee = "okafor"
    for (payee_key, (year, month)), cost in sorted(cost_by_payee_month.items()):
        next_month = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=timezone.utc)
        paid_on = next_month + timedelta(days=rng.randint(1, 6), hours=rng.randint(8, 20))
        if paid_on > now:
            continue
        if payee_key == late_payee and (now - paid_on).days < 35:
            continue
        payee = payees[payee_key]
        payments.append(
            Payment(
                user=user,
                payee=payee,
                amount=Decimal(f"{cost:.2f}"),
                payment_date=paid_on,
                payment_reference=f"{payee.bank_reference_pattern} {next_month:%b}".upper(),
            )
        )
    Payment.objects.bulk_create(payments)

    return {"students": len(STUDENTS), "payees": len(payees), "sessions": session_count, "payments": len(payments)}
