from django.urls import path

from . import students_views, views

urlpatterns = [
    path("login", views.login_view, name="web-login"),
    path("logout", views.logout_view, name="web-logout"),
    path("dashboard", views.dashboard_view, name="web-dashboard"),
    path("students", students_views.students_index, name="web-students-list"),
    path("students/new", students_views.students_new, name="web-students-new"),
    path("students/<uuid:student_id>", students_views.student_detail, name="web-student-detail"),
    path("students/<uuid:student_id>/update", students_views.student_update, name="web-student-update"),
    path("students/<uuid:student_id>/toggle-active", students_views.student_toggle_active, name="web-student-toggle-active"),
    path("students/<uuid:student_id>/delete", students_views.student_delete, name="web-student-delete"),
]
