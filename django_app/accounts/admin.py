from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_active", "is_staff", "assistant_limit")
    list_filter = ("is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="TutorHub AI limit", ordering="assistant_daily_limit")
    def assistant_limit(self, user):
        return "Unlimited" if user.assistant_daily_limit is None else f"{user.assistant_daily_limit} / day"

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "address")}),
        ("TutorHub AI", {"fields": ("assistant_daily_limit",)}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "password1", "password2"),
            },
        ),
    )
