from django.urls import path

from .views import FilterOptionsView, TrendsView

urlpatterns = [
    path("trends", TrendsView.as_view(), name="analytics-trends"),
    path("filters", FilterOptionsView.as_view(), name="analytics-filters"),
]
