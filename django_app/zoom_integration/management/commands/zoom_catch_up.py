from django.core.management.base import BaseCommand

from zoom_integration import autolog
from zoom_integration.models import ZoomToken


class Command(BaseCommand):
    help = "Log Zoom lessons from the last week that TutorHub missed, for every tutor with Zoom connected."

    def handle(self, *args, **options):
        for token in ZoomToken.objects.select_related("user"):
            try:
                counts = autolog.sweep(token.user)
            except Exception as exc:  # one tutor's failure shouldn't stop the rest
                self.stderr.write(f"Zoom catch-up failed for user {token.user_id}: {exc}")
                continue
            self.stdout.write(f"Zoom catch-up for user {token.user_id}: {counts}")
