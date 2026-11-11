"""Payee balances.

balance = payments received - cost of billable sessions (hours * the
student's hourly_rate). Negative means the payee owes money; positive means
they are in credit. Students without an hourly rate are not billed.

Durations are summed in Python rather than with database interval maths so
the result is identical on SQLite (tests) and Postgres (production).
"""

from collections import defaultdict

from django.db.models import Sum

from tutoring_sessions.models import Session

from .models import Payee, Payment


def payee_balances(payees) -> dict:
    """Balance for each payee in `payees`, keyed by payee id, in two queries."""
    payee_ids = [p.id for p in payees]
    if not payee_ids:
        return {}

    paid = defaultdict(float)
    for payee_id, total in Payment.objects.filter(payee_id__in=payee_ids).values_list("payee_id").annotate(total=Sum("amount")):
        paid[payee_id] = float(total or 0)

    cost = defaultdict(float)
    sessions = Session.objects.filter(student__payee_id__in=payee_ids, student__hourly_rate__isnull=False).values_list(
        "student__payee_id", "session_start_time", "session_end_time", "student__hourly_rate"
    )
    for payee_id, start, end, hourly_rate in sessions:
        cost[payee_id] += (end - start).total_seconds() / 3600 * hourly_rate

    return {payee_id: round(paid[payee_id] - cost[payee_id], 2) for payee_id in payee_ids}


def payee_balance(payee: Payee) -> float:
    return payee_balances([payee])[payee.id]
