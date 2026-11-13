from django.urls import path

from .views import DashboardRevenueView, DashboardStudentsView, DashboardUpcomingView, DashboardView, FilterOptionsView, TrendsView

urlpatterns = [
    path("dashboard", DashboardView.as_view(), name="analytics-dashboard"),
    path("dashboard/revenue", DashboardRevenueView.as_view(), name="analytics-dashboard-revenue"),
    path("dashboard/upcoming", DashboardUpcomingView.as_view(), name="analytics-dashboard-upcoming"),
    path("dashboard/students", DashboardStudentsView.as_view(), name="analytics-dashboard-students"),
    path("trends", TrendsView.as_view(), name="analytics-trends"),
    path("filters", FilterOptionsView.as_view(), name="analytics-filters"),
]
