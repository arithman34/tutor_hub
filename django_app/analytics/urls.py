from django.urls import path

from .views import DashboardView, FilterOptionsView, TrendsView

urlpatterns = [
    path("dashboard", DashboardView.as_view(), name="analytics-dashboard"),
    path("trends", TrendsView.as_view(), name="analytics-trends"),
    path("filters", FilterOptionsView.as_view(), name="analytics-filters"),
]
