from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "user", "level", "is_active", "created_at")
    list_filter = ("is_active", "level")
    search_fields = ("first_name", "last_name", "user__email")
    autocomplete_fields = ("user",)
