from django.urls import path

from . import sessions_views, students_views, views

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
    path("sessions", sessions_views.sessions_index, name="web-sessions-list"),
    path("sessions/new", sessions_views.sessions_new, name="web-sessions-new"),
    path("sessions/zoom-parse", sessions_views.sessions_zoom_parse, name="web-sessions-zoom-parse"),
    path("sessions/<uuid:session_id>", sessions_views.session_detail, name="web-session-detail"),
    path("sessions/<uuid:session_id>/update", sessions_views.session_update, name="web-session-update"),
    path("sessions/<uuid:session_id>/delete", sessions_views.session_delete, name="web-session-delete"),
]
