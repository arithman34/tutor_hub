from django.urls import path

from .views import (
    CallbackView,
    ConnectView,
    DisconnectView,
    OneOffEventView,
    RecurringEventsView,
    StatusView,
    UpcomingEventsView,
)

urlpatterns = [
    path("connect", ConnectView.as_view(), name="calendar-connect"),
    path("callback", CallbackView.as_view(), name="calendar-callback"),
    path("status", StatusView.as_view(), name="calendar-status"),
    path("disconnect", DisconnectView.as_view(), name="calendar-disconnect"),
    path("events/upcoming", UpcomingEventsView.as_view(), name="calendar-events-upcoming"),
    path("events", OneOffEventView.as_view(), name="calendar-events"),
    path("events/recurring", RecurringEventsView.as_view(), name="calendar-events-recurring"),
]
