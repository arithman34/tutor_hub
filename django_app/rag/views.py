from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Document
from .serializers import DocumentSerializer, DocumentUploadSerializer, QuerySerializer


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        return Document.objects.all()

    def create(self, request, *args, **kwargs):
        upload = DocumentUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        data = upload.validated_data

        try:
            document = services.ingest_document(
                file_bytes=data["file"].read(),
                title=data["title"],
                document_type=data["document_type"],
                subject=data["subject"],
                level=data["level"],
                source_filename=data["file"].name,
                exam_board=data.get("exam_board"),
                student_id=data.get("student_id"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)


class QueryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = QuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        question = data.pop("question")
        result = services.answer_question(question, data)
        return Response(result)
