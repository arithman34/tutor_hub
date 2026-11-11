import json
import os
from datetime import datetime, timezone

import boto3
from django.core.management.base import BaseCommand, CommandError

from web.data_transfer import build_full_backup


class Command(BaseCommand):
    """Writes a full backup (every account and row, see
    web.data_transfer.build_full_backup) to the backups S3 bucket, under
    exports/. Intended to run on a
    schedule (see terraform/environments/cost-optimized/backup.tf) rather
    than interactively.
    """

    help = "Export all data as JSON and upload it to the backups S3 bucket"

    def handle(self, *args, **options):
        bucket = os.environ.get("BACKUP_BUCKET")
        if not bucket:
            raise CommandError("BACKUP_BUCKET is not set")

        data = build_full_backup()
        key = f"exports/tutorhub_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

        s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION"))
        s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(data, indent=2).encode("utf-8"), ContentType="application/json")

        counts = {k: len(v) for k, v in data.items() if isinstance(v, list)}
        self.stdout.write(self.style.SUCCESS(f"Uploaded s3://{bucket}/{key} ({counts})"))
