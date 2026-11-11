from django.contrib import admin

from .models import AssistantUsage


@admin.register(AssistantUsage)
class AssistantUsageAdmin(admin.ModelAdmin):
    list_display = ("user", "day", "questions")
    list_filter = ("day",)
    search_fields = ("user__email",)
    ordering = ("-day",)
    readonly_fields = ("user", "day", "questions")

    def has_add_permission(self, request):
        return False
