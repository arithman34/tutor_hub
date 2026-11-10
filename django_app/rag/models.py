import uuid

from django.db import models
from pgvector.django import VectorField

EMBEDDING_DIMENSIONS = 1536


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=50)
    subject = models.CharField(max_length=100)
    level = models.CharField(max_length=50)
    exam_board = models.CharField(max_length=100, null=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.SET_NULL, null=True, blank=True, related_name="documents")
    source_url = models.CharField(max_length=255, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "documents"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title


class Chunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    content = models.TextField()
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS)
    page_number = models.IntegerField(null=True, blank=True)
    chunk_index = models.IntegerField()

    class Meta:
        db_table = "chunks"
        ordering = ["document", "chunk_index"]

    def __str__(self):
        return f"{self.document_id} chunk {self.chunk_index}"
