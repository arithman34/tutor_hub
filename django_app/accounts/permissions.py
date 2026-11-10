from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Mirrors User.is_admin from the FastAPI app (role in admin/admin_tutor)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsTutor(BasePermission):
    """Mirrors User.is_tutor from the FastAPI app (role in tutor/admin_tutor)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_tutor)
