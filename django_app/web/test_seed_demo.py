from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from accounts.models import User
from analytics.dashboard import get_dashboard_stats
from billing.models import Payment
from billing.services import payee_balances
from students.models import Student
from tutoring_sessions.models import Session


def seed(**options):
    out = StringIO()
    call_command("seed_demo", stdout=out, **options)
    return out.getvalue()


@override_settings(DEBUG=True)
class SeedDemoTests(TestCase):
    def test_creates_a_year_of_data_the_pages_can_show(self):
        output = seed(password="demo-pass-123")

        user = User.objects.get(email="demo@tutorhub.test")
        self.assertTrue(user.check_password("demo-pass-123"))
        self.assertIn("Sign in at /app/login as demo@tutorhub.test", output)

        self.assertEqual(Student.objects.filter(user=user).count(), 9)
        self.assertEqual(Student.objects.filter(user=user, is_active=False).count(), 2)
        sessions = Session.objects.filter(user=user)
        self.assertGreater(sessions.count(), 200)
        self.assertTrue(sessions.filter(is_no_show=True).exists())
        self.assertTrue(sessions.exclude(work_covered=None).exists())
        # A no-show never has notes.
        self.assertFalse(sessions.filter(is_no_show=True).exclude(work_covered=None).exists())

        stats = get_dashboard_stats(user)
        self.assertGreater(stats["revenue_this_year"], 0)
        self.assertGreater(stats["outstanding_total"], 0)

        # Most families are settled up to last month; at least one owes more.
        balances = payee_balances(list(user.payees.all()))
        self.assertTrue(any(balance < 0 for balance in balances.values()))

    def test_is_repeatable_and_replaces_the_previous_demo_data(self):
        seed()
        first = (Session.objects.count(), Payment.objects.count())
        seed()
        self.assertEqual((Session.objects.count(), Payment.objects.count()), first)
        self.assertEqual(User.objects.filter(email="demo@tutorhub.test").count(), 1)

    def test_leaves_other_accounts_alone(self):
        real = User.objects.create_user(email="tutor@gmail.com", password="x", first_name="A", last_name="B")
        Student.objects.create(user=real, first_name="Sam", last_name="Smith")
        seed()
        self.assertEqual(Student.objects.filter(user=real).count(), 1)

    def test_refuses_an_email_that_could_be_real(self):
        User.objects.create_user(email="tutor@gmail.com", password="x", first_name="A", last_name="B")
        with self.assertRaisesMessage(CommandError, "reserved test domain"):
            seed(email="tutor@gmail.com")
        self.assertTrue(User.objects.get(email="tutor@gmail.com").check_password("x"))

    @override_settings(DEBUG=False)
    def test_refuses_to_run_without_debug(self):
        with self.assertRaisesMessage(CommandError, "only runs with DEBUG on"):
            seed()
        self.assertFalse(User.objects.filter(email="demo@tutorhub.test").exists())
