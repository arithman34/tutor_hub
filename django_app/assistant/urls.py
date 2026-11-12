from django.urls import path

from .views import AskView, ConversationView, ResetView

urlpatterns = [
    path("", ConversationView.as_view(), name="assistant-conversation"),
    path("ask", AskView.as_view(), name="assistant-ask"),
    path("reset", ResetView.as_view(), name="assistant-reset"),
]
