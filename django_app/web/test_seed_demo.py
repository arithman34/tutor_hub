from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from accounts.models import User
from students.models import Student
from tutoring_sessions.models import Session


def seed(**options):
    out = StringIO()
    call_command("seed_demo", stdout=out, **options)
    return out.getvalue()


class SeedDemoTests(TestCase):
    def test_creates_the_demo_account_with_no_password(self):
        output = seed()
        user = User.objects.get(email="demo@tutorhub.test")
        self.assertTrue(user.is_demo)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(Student.objects.filter(user=user).count(), 9)
        self.assertIn("Try the demo", output)

    def test_months_sets_how_far_back_the_history_goes(self):
        seed(months=3)
        short = Session.objects.count()
        seed(months=24)
        self.assertGreater(Session.objects.count(), short * 3)

    @override_settings(DEBUG=True)
    def test_password_allows_a_local_password_login(self):
        output = seed(password="demo-pass-123")
        self.assertTrue(User.objects.get(email="demo@tutorhub.test").check_password("demo-pass-123"))
        self.assertIn("Sign in at /app/login as demo@tutorhub.test", output)
        # Running it again without one makes the password unusable again.
        seed()
        self.assertFalse(User.objects.get(email="demo@tutorhub.test").has_usable_password())

    @override_settings(DEBUG=False)
    def test_password_needs_debug(self):
        with self.assertRaisesMessage(CommandError, "only works with DEBUG on"):
            seed(password="demo-pass-123")
        self.assertFalse(User.objects.exists())

    def test_never_touches_a_real_account_with_the_demo_email(self):
        User.objects.create_user(email="demo@tutorhub.test", password="x", first_name="A", last_name="B")
        with self.assertRaisesMessage(CommandError, "is a real account"):
            seed()
        self.assertTrue(User.objects.get(email="demo@tutorhub.test").check_password("x"))

    def test_rejects_out_of_range_months(self):
        with self.assertRaisesMessage(CommandError, "between 1 and 24"):
            seed(months=30)
