"""Keeps the demo account read-only.

Applied to every API view by default (REST_FRAMEWORK in settings). The demo
account is shared by everyone who clicks "Try the demo", so nothing one
visitor does may change what the next one sees: it can read anything but
not create, edit or delete. A view that is harmless for the demo to call,
like asking TutorHub AI (the chat lives in each visitor's own browser
session), opts back in with `demo_can_write = True`.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

DEMO_READ_ONLY = "This is the read-only demo, so changes can't be saved."


class DemoIsReadOnly(BasePermission):
    message = DEMO_READ_ONLY

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS or getattr(view, "demo_can_write", False):
            return True
        return not getattr(request.user, "is_demo", False)
