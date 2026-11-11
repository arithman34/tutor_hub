import json

from django.core.management.base import BaseCommand, CommandError

from web.data_transfer import restore_full_backup


class Command(BaseCommand):
    """Imports a data export produced by the original FastAPI app.

    That export's shape is identical to a full backup produced here
    (web.data_transfer.build_full_backup), except user rows use
    `hashed_password` (a raw passlib bcrypt hash, e.g. "$2b$12$...") instead
    of `password`. Django's check_password() only
    recognises a bcrypt hash when it's prefixed with the hasher's algorithm
    label, so each hash is rewritten to "bcrypt$<hash>" on the way in — see
    the BCryptPasswordHasher entry added to settings.PASSWORD_HASHERS.

    This wipes and replaces every users/payees/students/sessions/payments
    row — run it only against a database you intend to overwrite.
    """

    help = "Import a FastAPI-app data export (wipes and replaces existing data)"

    def add_arguments(self, parser):
        parser.add_argument("export_path")

    def handle(self, *args, **options):
        path = options["export_path"]
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except OSError as exc:
            raise CommandError(f"Could not read {path}: {exc}")

        for row in data.get("users", []):
            legacy_hash = row.pop("hashed_password", None)
            if legacy_hash is not None:
                row["password"] = legacy_hash if legacy_hash.startswith("bcrypt$") else f"bcrypt${legacy_hash}"

        counts = {k: len(v) for k, v in data.items() if isinstance(v, list)}
        restore_full_backup(data)
        self.stdout.write(self.style.SUCCESS(f"Imported: {counts}"))
