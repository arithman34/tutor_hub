"""My Data: download or replace everything the signed-in account owns.

See data_transfer.py for what the file contains and how an import is checked.
"""

import json
from datetime import datetime, timezone

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .data_transfer import build_user_export, import_user_data

# Far more than a tutor's lifetime of records, but stops a huge upload from
# being read into memory.
MAX_IMPORT_BYTES = 20 * 1024 * 1024

_ImportCountsSerializer = inline_serializer(
    "ImportCounts",
    {
        "payees": serializers.IntegerField(),
        "students": serializers.IntegerField(),
        "sessions": serializers.IntegerField(),
        "payments": serializers.IntegerField(),
    },
)


class DataExportView(APIView):
    @extend_schema(
        summary="Download all your data",
        description="A JSON file (sent as an attachment) of your payees, students, sessions and payments.",
        responses={(200, "application/json"): OpenApiTypes.OBJECT},
    )
    def get(self, request):
        data = build_user_export(request.user)
        filename = f"tutorhub_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class DataImportView(APIView):
    parser_classes = [MultiPartParser]

    @extend_schema(
        summary="Replace all your data from an export file",
        description="Deletes your current payees, students, sessions and payments and loads the file's instead. Nothing changes if the file has any problem.",
        request={"multipart/form-data": inline_serializer("DataImport", {"file": serializers.FileField()})},
        responses={200: _ImportCountsSerializer, 400: OpenApiResponse(description="Missing, too large or invalid file.")},
    )
    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Choose a file to import."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_IMPORT_BYTES:
            return Response({"detail": "File is too large."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = json.loads(upload.read())
            if not isinstance(data, dict):
                raise ValueError("The file isn't a TutorHub export.")
            counts = import_user_data(request.user, data)
        except (ValueError, KeyError, TypeError, DjangoValidationError, DatabaseError) as exc:
            # json.JSONDecodeError and UnicodeDecodeError are ValueErrors too.
            return Response({"detail": f"Import failed: {exc or type(exc).__name__}"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(counts)
