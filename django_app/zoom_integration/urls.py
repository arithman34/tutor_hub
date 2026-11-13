from django.urls import path

from .views import CallbackView, ConnectView, DisconnectView, StatusView, SweepView, WebhookView

urlpatterns = [
    path("connect", ConnectView.as_view(), name="zoom-connect"),
    path("callback", CallbackView.as_view(), name="zoom-callback"),
    path("status", StatusView.as_view(), name="zoom-status"),
    path("disconnect", DisconnectView.as_view(), name="zoom-disconnect"),
    path("webhook", WebhookView.as_view(), name="zoom-webhook"),
    path("sweep", SweepView.as_view(), name="zoom-sweep"),
]
