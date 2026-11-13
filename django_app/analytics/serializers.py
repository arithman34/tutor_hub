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
    """Headline numbers from analytics.dashboard.get_dashboard_stats.

    Month-on-month changes compare month-to-date with the same days of last
    month (compare_from to compare_to), not with the whole of last month.
    """

    revenue_alltime = serializers.FloatField()
    revenue_this_month = serializers.FloatField(help_text="Payments received this month so far.")
    revenue_this_year = serializers.FloatField()
    revenue_same_period_last_month = serializers.FloatField(help_text="Payments received from compare_from to compare_to.")
    revenue_projected = serializers.FloatField(
        allow_null=True,
        help_text="This month so far plus what the rest of last month brought in. Null with no revenue last month.",
    )
    revenue_month_to_date = serializers.ListField(
        child=serializers.FloatField(), help_text="Running total of this month's payments, one value per day so far."
    )
    mom_trend = serializers.FloatField(allow_null=True, help_text="Revenue percent change against the same days last month.")
    compare_from = serializers.DateField(help_text="First day of last month's comparison period.")
    compare_to = serializers.DateField(help_text="Last day (inclusive) of last month's comparison period.")
    outstanding_total = serializers.FloatField(help_text="Total owed by payees in arrears.")
    outstanding_payees = serializers.IntegerField()
    average_hourly_rate = serializers.FloatField(
        allow_null=True, help_text="Revenue this year divided by hours taught this year. Null before any hours."
    )
    hours_this_year = serializers.FloatField()
    active_students = serializers.IntegerField()
    students_taught_this_month = serializers.IntegerField()
    sessions_this_week = serializers.IntegerField(help_text="Sessions in the last 7 days.")
    sessions_week_pct_change = serializers.FloatField(allow_null=True, help_text="Against the 7 days before that.")
    sessions_this_month = serializers.IntegerField()
    sessions_pct_change = serializers.FloatField(allow_null=True, help_text="Against the same days last month.")
    hours_this_month = serializers.FloatField()
    hours_pct_change = serializers.FloatField(allow_null=True, help_text="Against the same days last month.")


class RevenueMonthSerializer(serializers.Serializer):
    month = serializers.DateField(help_text="First day of the month.")
    revenue = serializers.FloatField(help_text="Payments received that month.")
    in_progress = serializers.BooleanField(help_text="True for the current month.")


class RevenueByMonthSerializer(serializers.Serializer):
    months = RevenueMonthSerializer(many=True, help_text="The last 12 months, oldest first.")


class UpcomingQuerySerializer(serializers.Serializer):
    days = serializers.IntegerField(
        required=False, default=4, min_value=1, max_value=14, help_text="How many days to cover, today being the first."
    )


class UpcomingSessionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    student_id = serializers.UUIDField()
    student_name = serializers.CharField()
    level = serializers.CharField(allow_null=True, help_text="The student's level, e.g. GCSE.")
    topic_tags = serializers.CharField(allow_null=True)
    start = serializers.DateTimeField(help_text="Wall-clock time, labelled UTC.")
    end = serializers.DateTimeField()


class UpcomingSessionsSerializer(serializers.Serializer):
    sessions = UpcomingSessionSerializer(many=True, help_text="Soonest first, at most 12.")


class StudentBreakdownRowSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    student_name = serializers.CharField()
    sessions = serializers.IntegerField()
    hours = serializers.FloatField()
    revenue = serializers.FloatField(help_text="Hours times the student's hourly rate.")
    hourly_rate = serializers.FloatField(allow_null=True)


class StudentBreakdownSerializer(serializers.Serializer):
    students = StudentBreakdownRowSerializer(many=True, help_text="Students taught this month so far, most revenue first.")
