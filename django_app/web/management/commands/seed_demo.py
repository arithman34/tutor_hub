"""Create the demo account, or regenerate its made-up records now.

The homepage's "Try the demo" button already does both on its own (see
accounts/demo.py), so this is for local screenshots and for trying other
history lengths:

    python manage.py seed_demo                          # 12 months of records
    python manage.py seed_demo --months 24 --seed 7
    python manage.py seed_demo --password demo-pass     # local only: log in with a password

It only ever touches the demo account, never a real one.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts import demo


class Command(BaseCommand):
    help = "Create the read-only demo account, or regenerate its made-up students, sessions and payments."

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=demo.DEFAULT_MONTHS, help="How far back the history goes (at most 24).")
        parser.add_argument("--seed", type=int, default=demo.DEFAULT_SEED, help="Random seed, so a rerun gives the same data.")
        parser.add_argument(
            "--password",
            help="Also allow logging in with this password (only with DEBUG on). Otherwise the Try the demo button is the only way in.",
        )

    def handle(self, *args, months, seed, password, **options):
        if not 1 <= months <= 24:
            raise CommandError("--months must be between 1 and 24.")
        if password and not settings.DEBUG:
            raise CommandError("--password only works with DEBUG on. In production, sign in with the Try the demo button.")

        try:
            user = demo.get_or_create_user()
        except demo.DemoUnavailable as exc:
            raise CommandError(str(exc)) from exc

        counts = demo.fill(user, months=months, seed=seed)
        user.set_password(password)  # None makes it unusable again.
        user.save(update_fields=["password"])

        self.stdout.write(self.style.SUCCESS(
            f"Demo account ready: {counts['students']} students, {counts['payees']} payees, "
            f"{counts['sessions']} sessions, {counts['payments']} payments."
        ))
        if password:
            self.stdout.write(f"Sign in at /app/login as {user.email} with that password, or use Try the demo on the homepage.")
        else:
            self.stdout.write("Sign in with the Try the demo button on the homepage.")
