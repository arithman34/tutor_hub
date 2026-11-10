from django.contrib import admin

from .models import Chunk, Document


class ChunkInline(admin.TabularInline):
    model = Chunk
    extra = 0
    fields = ("chunk_index", "page_number", "content")
    readonly_fields = ("chunk_index", "page_number", "content")
    can_delete = False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "document_type", "subject", "level", "exam_board", "uploaded_at")
    list_filter = ("document_type", "subject", "level")
    search_fields = ("title",)
    inlines = [ChunkInline]
