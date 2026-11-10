from django.urls import path

from . import views

urlpatterns = [
    path("login", views.login_view, name="web-login"),
    path("logout", views.logout_view, name="web-logout"),
    path("dashboard", views.dashboard_view, name="web-dashboard"),
]
