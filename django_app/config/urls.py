from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

urlpatterns = [
    path("health", lambda request: HttpResponse("ok")),
    # Django's own admin site is moved off /admin/ — the web app's own
    # /admin/users and /admin/data pages (ported from the FastAPI app) use
    # that path, and Django admin's catch-all view would otherwise swallow
    # them with a login redirect before web.urls ever sees the request.
    path("django-admin/", admin.site.urls),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/students/", include("students.urls")),
    path("api/v1/sessions/", include("tutoring_sessions.urls")),
    path("api/v1/", include("billing.urls")),
    path("api/v1/", include("rag.urls")),
    path("api/v1/calendar/", include("calendar_integration.urls")),
    path("api/v1/analytics/", include("analytics.urls")),
    path("", include("web.urls")),
]
