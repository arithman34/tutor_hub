from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from accounts.data_views import DataExportView, DataImportView
from accounts.views import SetupView

from .spa import spa_index

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
    path("api/v1/calendar/", include("calendar_integration.urls")),
    path("api/v1/zoom/", include("zoom_integration.urls")),
    path("api/v1/analytics/", include("analytics.urls")),
    path("api/v1/assistant/", include("assistant.urls")),
    path("api/v1/data/export", DataExportView.as_view(), name="data-export"),
    path("api/v1/data/import", DataImportView.as_view(), name="data-import"),
    path("api/v1/setup", SetupView.as_view(), name="setup"),
    # OpenAPI schema and Swagger UI. Both need a signed-in user, like the
    # rest of the API; the browser's auth cookie is enough to view the docs.
    path("api/v1/schema", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/v1/docs", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    # The React app. Any path under /app/ is one of its pages.
    re_path(r"^app(?:/(?P<path>.*))?$", spa_index, name="spa"),
    path("", include("web.urls")),
]
