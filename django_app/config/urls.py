from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/students/", include("students.urls")),
    path("api/v1/sessions/", include("tutoring_sessions.urls")),
]
