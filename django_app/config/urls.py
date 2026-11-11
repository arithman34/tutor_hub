from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

urlpatterns = [
    path("health", lambda request: HttpResponse("ok")),
    # Django's admin is the platform operator's view across all accounts
    # (superuser only). It lives off the conventional /admin/ path so it
    # isn't the first URL a scanner tries.
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
