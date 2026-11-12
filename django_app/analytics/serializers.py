from rest_framework import serializers


class TrendsQuerySerializer(serializers.Serializer):
    range = serializers.CharField(
        required=False, default="12m", help_text="3m, 6m, 12m, ytd or all. Unknown values fall back to 12m."
    )
    granularity = serializers.CharField(
        required=False, default="month", help_text="day, week or month. Coarsened automatically for long ranges."
    )
    start = serializers.DateField(required=False, allow_null=True, help_text="With end, overrides range.")
    end = serializers.DateField(required=False, allow_null=True)
    student_id = serializers.UUIDField(required=False, allow_null=True)
    payee_id = serializers.UUIDField(required=False, allow_null=True)


class TrendSeriesSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.ChoiceField(choices=["count", "hours", "currency"])
    type = serializers.ChoiceField(choices=["bar", "line"], help_text="How the series is drawn.")
    axis = serializers.ChoiceField(choices=["y", "y1"], help_text="Left (y) or right (y1) axis.")
    data = serializers.ListField(child=serializers.FloatField(), help_text="One value per label.")
    total = serializers.FloatField(help_text="Sum over the window, or the last value for running totals.")
    change = serializers.FloatField(allow_null=True, help_text="Percent change against the previous window of equal length.")


class TrendChartSerializer(serializers.Serializer):
    key = serializers.CharField()
    title = serializers.CharField()
    series = TrendSeriesSerializer(many=True)


class TrendsSerializer(serializers.Serializer):
    range = serializers.CharField(help_text="The preset applied, or custom when start/end were given.")
    granularity = serializers.CharField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    labels = serializers.ListField(child=serializers.DateTimeField(), help_text="Start of each bucket.")
    charts = TrendChartSerializer(many=True)


class FilterOptionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class FilterOptionsSerializer(serializers.Serializer):
    students = FilterOptionSerializer(many=True)
    payees = FilterOptionSerializer(many=True)


class DashboardSerializer(serializers.Serializer):
    """Headline numbers from analytics.dashboard.get_dashboard_stats."""

    revenue_alltime = serializers.FloatField()
    revenue_this_month = serializers.FloatField()
    revenue_this_year = serializers.FloatField()
    mom_trend = serializers.FloatField(allow_null=True, help_text="Revenue percent change against last month.")
    outstanding_total = serializers.FloatField(help_text="Total owed by payees in arrears.")
    outstanding_payees = serializers.IntegerField()
    active_students = serializers.IntegerField()
    sessions_this_week = serializers.IntegerField(help_text="Sessions in the last 7 days.")
    sessions_this_month = serializers.IntegerField()
    sessions_pct_change = serializers.FloatField(allow_null=True)
    hours_this_month = serializers.FloatField()
    hours_pct_change = serializers.FloatField(allow_null=True)
