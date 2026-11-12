import re

from django.urls import path, re_path

from calendar_integration.views import GoogleRedirectView

from . import views

urlpatterns = [
    path("", views.home_view, name="web-home"),
    path("privacy", views.privacy_view, name="web-privacy"),
    path("demo", views.demo_view, name="web-demo"),
    # The redirect URI registered with Google; it redirects on to /app/connections.
    path("calendar/callback", GoogleRedirectView.as_view(), name="web-calendar-callback"),
    re_path(
        rf"^(?P<prefix>{'|'.join(map(re.escape, views.MOVED_PREFIXES))})(?:/(?P<rest>.*))?$",
        views.moved_to_app,
        name="web-moved",
    ),
]
