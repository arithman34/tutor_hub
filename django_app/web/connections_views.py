from django.shortcuts import render

from calendar_integration.models import GoogleCalendarToken

from .auth import login_required

_ERROR_MESSAGES = {
    "access_denied": "Google access was denied. Please try connecting again.",
    "invalid_state": "Security check failed. Please try connecting again.",
    "token_exchange_failed": "Failed to complete Google authentication. Please try again.",
    "not_connected": "Connect Google Calendar before creating sessions.",
}


@login_required
def connections_page(request):
    user = request.user
    token = GoogleCalendarToken.objects.filter(user=user).first()
    google_connected = bool(token and token.is_connected)

    return render(
        request,
        "connections/index.html",
        {
            "user": user,
            "active_page": "connections",
            "google_connected": google_connected,
            "connected_flash": request.GET.get("connected"),
            "error_msg": _ERROR_MESSAGES.get(request.GET.get("error")),
        },
    )
