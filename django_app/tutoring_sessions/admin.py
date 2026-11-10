from django.contrib import admin

from .models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("student", "user", "session_date", "minutes", "is_no_show")
    list_filter = ("is_no_show", "session_date")
    search_fields = ("student__first_name", "student__last_name", "user__email")
    autocomplete_fields = ("user", "student")
    date_hierarchy = "session_date"
