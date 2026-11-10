from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DocumentViewSet, QueryView

router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="document")

urlpatterns = router.urls + [
    path("query", QueryView.as_view(), name="rag-query"),
]
