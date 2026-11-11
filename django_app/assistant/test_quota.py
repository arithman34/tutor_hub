from datetime import date, datetime, timezone

from django.contrib.admin.sites import site
from django.test import TestCase

from accounts.models import User

from .models import AssistantUsage
from .quota import Allowance, QuotaExceeded, get_allowance, refund_question, reserve_question, uk_today

# 23:30 UTC on 1 July is 00:30 on 2 July in London (BST).
LATE_UTC = datetime(2026, 7, 1, 23, 30, tzinfo=timezone.utc)


def make_user(email, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", **extra)


class AllowanceTests(TestCase):
    def test_limited(self):
        allowance = Allowance(limit=3, used=1)
        self.assertEqual((allowance.unlimited, allowance.remaining, allowance.exhausted), (False, 2, False))

    def test_exhausted_never_goes_negative(self):
        allowance = Allowance(limit=1, used=2)
        self.assertEqual((allowance.remaining, allowance.exhausted), (0, True))

    def test_unlimited(self):
        allowance = Allowance(limit=None, used=50)
        self.assertEqual((allowance.unlimited, allowance.remaining, allowance.exhausted), (True, None, False))


class QuotaTests(TestCase):
    def setUp(self):
        self.user = make_user("tutor@example.com")

    def test_new_accounts_get_one_question_a_day(self):
        self.assertEqual(get_allowance(self.user), Allowance(limit=1, used=0))

    def test_uk_today_uses_london_time(self):
        self.assertEqual(uk_today(LATE_UTC), date(2026, 7, 2))

    def test_reserve_counts_against_the_uk_day(self):
        self.assertEqual(reserve_question(self.user, now=LATE_UTC), date(2026, 7, 2))
        self.assertEqual(get_allowance(self.user, now=LATE_UTC), Allowance(limit=1, used=1))

    def test_reserve_refuses_once_limit_reached(self):
        reserve_question(self.user, now=LATE_UTC)
        with self.assertRaises(QuotaExceeded):
            reserve_question(self.user, now=LATE_UTC)
        self.assertEqual(AssistantUsage.objects.get(user=self.user).questions, 1)

    def test_allowance_resets_the_next_uk_day(self):
        reserve_question(self.user, now=LATE_UTC)
        tomorrow = datetime(2026, 7, 2, 23, 0, tzinfo=timezone.utc)  # 00:00 on 3 July in London
        self.assertEqual(get_allowance(self.user, now=tomorrow).used, 0)
        reserve_question(self.user, now=tomorrow)

    def test_unlimited_accounts_are_never_refused_but_still_counted(self):
        self.user.assistant_daily_limit = None
        self.user.save()
        for _ in range(5):
            reserve_question(self.user, now=LATE_UTC)
        self.assertEqual(get_allowance(self.user, now=LATE_UTC), Allowance(limit=None, used=5))

    def test_admin_change_applies_to_a_stale_user_object(self):
        stale = User.objects.get(pk=self.user.pk)
        User.objects.filter(pk=self.user.pk).update(assistant_daily_limit=None)
        reserve_question(stale, now=LATE_UTC)
        reserve_question(stale, now=LATE_UTC)

    def test_zero_limit_blocks_every_question(self):
        self.user.assistant_daily_limit = 0
        self.user.save()
        with self.assertRaises(QuotaExceeded):
            reserve_question(self.user)

    def test_refund_gives_the_question_back(self):
        day = reserve_question(self.user, now=LATE_UTC)
        refund_question(self.user, day)
        self.assertEqual(get_allowance(self.user, now=LATE_UTC).used, 0)
        reserve_question(self.user, now=LATE_UTC)

    def test_refund_never_goes_below_zero(self):
        day = reserve_question(self.user, now=LATE_UTC)
        refund_question(self.user, day)
        refund_question(self.user, day)
        self.assertEqual(AssistantUsage.objects.get(user=self.user).questions, 0)

    def test_usage_is_per_account(self):
        other = make_user("other@example.com")
        reserve_question(self.user, now=LATE_UTC)
        self.assertEqual(get_allowance(other, now=LATE_UTC).used, 0)
        reserve_question(other, now=LATE_UTC)


class AdminTests(TestCase):
    def test_limit_is_editable_on_the_user_admin(self):
        user_admin = site._registry[User]
        fields = [field for _, options in user_admin.fieldsets for field in options["fields"]]
        self.assertIn("assistant_daily_limit", fields)

    def test_limit_column_shows_unlimited(self):
        user_admin = site._registry[User]
        self.assertEqual(user_admin.assistant_limit(User(assistant_daily_limit=None)), "Unlimited")
        self.assertEqual(user_admin.assistant_limit(User(assistant_daily_limit=1)), "1 / day")

    def test_usage_is_registered_read_only(self):
        self.assertFalse(site._registry[AssistantUsage].has_add_permission(request=None))
