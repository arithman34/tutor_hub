import inspect
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session

from . import tools
from .tools import (
    TOOL_SPECS,
    TOOLS,
    ToolError,
    count_sessions,
    find_students,
    get_payments,
    get_sessions,
    list_payee_balances,
    list_students,
    run_tool,
)


def make_user(email):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B")


def make_session(user, student, start, minutes=60, **fields):
    return Session.objects.create(
        user=user,
        student=student,
        session_date=start,
        session_start_time=start,
        session_end_time=start + timedelta(minutes=minutes),
        **fields,
    )


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


class AssistantTestCase(TestCase):
    """An owner with two students sharing one payee, and another account with lookalike data."""

    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other = make_user("other@example.com")

        self.payee = Payee.objects.create(
            user=self.owner,
            first_name="Mei",
            last_name="Chan",
            email="mei@example.com",
            phone_number="+447700900000",
            bank_reference_pattern="CHAN TUITION",
        )
        self.lok = Student.objects.create(user=self.owner, first_name="Lok", last_name="Chan", level="GCSE", hourly_rate=40, payee=self.payee)
        self.kit = Student.objects.create(user=self.owner, first_name="Kit", last_name="Chan", level="A-Level", hourly_rate=50, payee=self.payee)

        self.other_payee = Payee.objects.create(user=self.other, first_name="Mei", last_name="Chan")
        self.other_lok = Student.objects.create(user=self.other, first_name="Lok", last_name="Chan", hourly_rate=40, payee=self.other_payee)


class FindStudentsTests(AssistantTestCase):
    def test_matches_partial_first_name_case_insensitively(self):
        result = find_students(self.owner, "lo")
        self.assertEqual([s["id"] for s in result["students"]], [str(self.lok.id)])

    def test_every_word_must_match(self):
        result = find_students(self.owner, "Lok Chan")
        self.assertEqual([s["name"] for s in result["students"]], ["Lok Chan"])

    def test_returns_all_matches_when_ambiguous(self):
        result = find_students(self.owner, "Chan")
        self.assertEqual([s["name"] for s in result["students"]], ["Kit Chan", "Lok Chan"])

    def test_includes_inactive_students_with_flag(self):
        self.lok.is_active = False
        self.lok.save()
        [student] = find_students(self.owner, "Lok")["students"]
        self.assertFalse(student["is_active"])

    def test_includes_payee_and_level(self):
        [student] = find_students(self.owner, "Lok")["students"]
        self.assertEqual(student["level"], "GCSE")
        self.assertEqual(student["payee"], {"id": str(self.payee.id), "name": "Mei Chan"})

    def test_student_without_payee(self):
        Student.objects.create(user=self.owner, first_name="Ada", last_name="Jones")
        [student] = find_students(self.owner, "Ada")["students"]
        self.assertIsNone(student["payee"])

    def test_no_match_returns_empty_list(self):
        self.assertEqual(find_students(self.owner, "Zed"), {"students": []})

    def test_never_returns_another_accounts_students(self):
        ids = {s["id"] for s in find_students(self.owner, "Lok")["students"]}
        self.assertNotIn(str(self.other_lok.id), ids)

    def test_blank_name_is_rejected(self):
        with self.assertRaises(ToolError):
            find_students(self.owner, "  ")


class ListStudentsTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.ada = Student.objects.create(user=self.owner, first_name="Ada", last_name="Smith", level="KS3")
        self.old = Student.objects.create(user=self.owner, first_name="Old", last_name="Pupil", is_active=False)
        make_session(self.owner, self.lok, utc(2026, 10, 30, 16))
        make_session(self.owner, self.lok, utc(2026, 11, 2, 16))
        make_session(self.owner, self.lok, utc(2026, 11, 9, 16), is_no_show=True)
        make_session(self.owner, self.kit, utc(2026, 10, 6, 17))
        make_session(self.owner, self.old, utc(2026, 11, 3, 17))
        make_session(self.other, self.other_lok, utc(2026, 11, 2, 16))

    def by_name(self, result):
        return {student["name"]: student for student in result["students"]}

    def test_lists_active_students_by_name_with_period_counts(self):
        result = list_students(self.owner, start="2026-11-01", end="2026-11-30")
        self.assertEqual(result["period"], {"start": "2026-11-01", "end": "2026-11-30"})
        self.assertEqual([s["name"] for s in result["students"]], ["Ada Smith", "Kit Chan", "Lok Chan"])
        counts = {name: s["sessions_in_period"] for name, s in self.by_name(result).items()}
        self.assertEqual(counts, {"Ada Smith": 0, "Kit Chan": 0, "Lok Chan": 2})

    def test_last_session_ignores_the_period(self):
        students = self.by_name(list_students(self.owner, start="2026-11-01", end="2026-11-30"))
        self.assertEqual(students["Kit Chan"]["last_session"], "2026-10-06T18:00+01:00")
        self.assertEqual(students["Lok Chan"]["last_session"], "2026-11-09T16:00+00:00")
        self.assertIsNone(students["Ada Smith"]["last_session"])

    def test_without_range_counts_all_sessions(self):
        result = list_students(self.owner)
        students = self.by_name(result)
        self.assertEqual(result["period"], {"start": None, "end": None})
        self.assertEqual(students["Lok Chan"]["sessions_in_period"], 3)
        self.assertEqual(students["Kit Chan"]["sessions_in_period"], 1)

    def test_include_inactive(self):
        students = self.by_name(list_students(self.owner, include_inactive=True, start="2026-11-01"))
        self.assertFalse(students["Old Pupil"]["is_active"])
        self.assertEqual(students["Old Pupil"]["sessions_in_period"], 1)

    def test_includes_payee_and_level(self):
        students = self.by_name(list_students(self.owner))
        self.assertEqual(students["Lok Chan"]["payee"], {"id": str(self.payee.id), "name": "Mei Chan"})
        self.assertEqual(students["Lok Chan"]["level"], "GCSE")
        self.assertIsNone(students["Ada Smith"]["payee"])

    def test_never_returns_another_accounts_students_or_sessions(self):
        result = list_students(self.owner, include_inactive=True)
        self.assertNotIn(str(self.other_lok.id), json.dumps(result))
        self.assertEqual(self.by_name(result)["Lok Chan"]["sessions_in_period"], 3)

    def test_never_includes_rates_or_external_ids(self):
        self.lok.zoom_meeting_id = "123456789"
        self.lok.save()
        text = json.dumps(list_students(self.owner))
        self.assertNotIn("hourly_rate", text)
        self.assertNotIn("123456789", text)

    def test_no_students(self):
        self.assertEqual(list_students(make_user("new@example.com"))["students"], [])

    def test_bad_arguments_are_rejected(self):
        for kwargs in ({"include_inactive": "yes"}, {"start": "November"}, {"start": "2026-11-30", "end": "2026-11-01"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ToolError):
                list_students(self.owner, **kwargs)


class CountSessionsTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        make_session(self.owner, self.lok, utc(2026, 10, 5, 16), minutes=60)
        make_session(self.owner, self.lok, utc(2026, 10, 12, 16), minutes=90)
        make_session(self.owner, self.lok, utc(2026, 10, 19, 16), minutes=60, is_no_show=True)
        make_session(self.owner, self.kit, utc(2026, 10, 6, 17), minutes=30)
        make_session(self.owner, self.lok, utc(2026, 11, 2, 16), minutes=60)
        make_session(self.other, self.other_lok, utc(2026, 10, 5, 16), minutes=60)

    def test_counts_one_student_in_range(self):
        result = count_sessions(self.owner, student_id=str(self.lok.id), start="2026-10-01", end="2026-10-31")
        self.assertEqual(result["student"], {"id": str(self.lok.id), "name": "Lok Chan"})
        self.assertEqual(result["period"], {"start": "2026-10-01", "end": "2026-10-31"})
        self.assertEqual(result["sessions"], 3)
        self.assertEqual(result["no_shows"], 1)
        self.assertEqual(result["hours_booked"], 3.5)
        self.assertEqual(result["hours_attended"], 2.5)

    def test_without_student_counts_all_own_students(self):
        result = count_sessions(self.owner, start="2026-10-01", end="2026-10-31")
        self.assertIsNone(result["student"])
        self.assertEqual(result["sessions"], 4)

    def test_without_range_counts_everything(self):
        self.assertEqual(count_sessions(self.owner)["sessions"], 5)

    def test_end_date_is_inclusive(self):
        result = count_sessions(self.owner, student_id=str(self.lok.id), start="2026-10-12", end="2026-10-12")
        self.assertEqual(result["sessions"], 1)

    def test_days_are_uk_days_not_utc_days(self):
        # 23:30 UTC on 1 July is 00:30 on 2 July in London (BST).
        make_session(self.owner, self.kit, utc(2026, 7, 1, 23, 30))
        self.assertEqual(count_sessions(self.owner, start="2026-07-01", end="2026-07-01")["sessions"], 0)
        self.assertEqual(count_sessions(self.owner, start="2026-07-02", end="2026-07-02")["sessions"], 1)

    def test_another_accounts_student_is_not_found(self):
        with self.assertRaisesMessage(ToolError, "No student found"):
            count_sessions(self.owner, student_id=str(self.other_lok.id))

    def test_bad_arguments_are_rejected(self):
        for kwargs in (
            {"student_id": "lok"},
            {"start": "01/10/2026"},
            {"end": 20261031},
            {"start": "2026-10-31", "end": "2026-10-01"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ToolError):
                count_sessions(self.owner, **kwargs)


class GetSessionsTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.older = make_session(self.owner, self.lok, utc(2026, 11, 2, 16), work_covered="Quadratics", topic_tags="algebra")
        self.newer = make_session(
            self.owner,
            self.lok,
            utc(2026, 11, 9, 16),
            minutes=45,
            work_covered="Simultaneous equations",
            student_actions="- Exercise 4B",
            tutor_actions="- Find past paper",
            next_lesson_focus="Inequalities",
            zoom_summary_raw="Full raw Zoom transcript",
            zoom_meeting_uuid="abc==",
            calendar_event_id="evt123",
        )
        make_session(self.owner, self.kit, utc(2026, 11, 3, 17), work_covered="Integration")
        make_session(self.other, self.other_lok, utc(2026, 11, 9, 16), work_covered="Other account notes")

    def test_returns_notes_newest_first(self):
        result = get_sessions(self.owner, student_id=str(self.lok.id))
        self.assertEqual([s["work_covered"] for s in result["sessions"]], ["Simultaneous equations", "Quadratics"])
        first = result["sessions"][0]
        self.assertEqual(first["start"], "2026-11-09T16:00+00:00")
        self.assertEqual(first["duration_minutes"], 45)
        self.assertEqual(first["next_lesson_focus"], "Inequalities")
        self.assertEqual(first["student"]["name"], "Lok Chan")

    def test_start_is_reported_in_uk_time(self):
        make_session(self.owner, self.kit, utc(2026, 7, 1, 15))
        [session] = get_sessions(self.owner, start="2026-07-01", end="2026-07-01")["sessions"]
        self.assertEqual(session["start"], "2026-07-01T16:00+01:00")

    def test_never_includes_raw_transcript_or_external_ids(self):
        payload = json.dumps(get_sessions(self.owner))
        for secret in ("Full raw Zoom transcript", "abc==", "evt123", "Other account notes"):
            self.assertNotIn(secret, payload)

    def test_without_student_covers_all_own_students(self):
        result = get_sessions(self.owner, start="2026-11-02", end="2026-11-08")
        self.assertEqual([s["student"]["name"] for s in result["sessions"]], ["Kit Chan", "Lok Chan"])

    def test_limit_truncates_and_reports_total(self):
        result = get_sessions(self.owner, limit=1)
        self.assertEqual(len(result["sessions"]), 1)
        self.assertEqual(result["total_matching"], 3)

    def test_total_matches_returned_when_under_limit(self):
        self.assertEqual(get_sessions(self.owner)["total_matching"], 3)

    def test_bad_limit_is_rejected(self):
        for limit in (0, tools.MAX_SESSIONS_LIMIT + 1, "5", True):
            with self.subTest(limit=limit), self.assertRaises(ToolError):
                get_sessions(self.owner, limit=limit)


class ListPayeeBalancesTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        # Mei: Lok 2h at £40 + Kit 1h at £50 = £130 owed, £100 paid -> -30.
        make_session(self.owner, self.lok, utc(2026, 11, 2, 16), minutes=120)
        make_session(self.owner, self.kit, utc(2026, 11, 3, 16), minutes=60)
        Payment.objects.create(user=self.owner, payee=self.payee, amount=Decimal("100.00"), payment_date=utc(2026, 11, 4))

        self.paid_up = Payee.objects.create(user=self.owner, first_name="Sam", last_name="Hill")
        Payment.objects.create(user=self.owner, payee=self.paid_up, amount=Decimal("20.00"), payment_date=utc(2026, 11, 4))

    def test_balances_sorted_most_owing_first(self):
        result = list_payee_balances(self.owner)
        self.assertEqual(result["currency"], "GBP")
        self.assertEqual(
            result["payees"],
            [
                {"id": str(self.payee.id), "name": "Mei Chan", "students": ["Kit Chan", "Lok Chan"], "balance": -30.0, "owes": True},
                {"id": str(self.paid_up.id), "name": "Sam Hill", "students": [], "balance": 20.0, "owes": False},
            ],
        )

    def test_only_owing_filters_out_payees_in_credit(self):
        result = list_payee_balances(self.owner, only_owing=True)
        self.assertEqual([p["name"] for p in result["payees"]], ["Mei Chan"])

    def test_never_includes_contact_or_bank_details(self):
        payload = json.dumps(list_payee_balances(self.owner))
        for secret in ("mei@example.com", "+447700900000", "CHAN TUITION"):
            self.assertNotIn(secret, payload)

    def test_never_includes_another_accounts_payees(self):
        ids = {p["id"] for p in list_payee_balances(self.owner)["payees"]}
        self.assertNotIn(str(self.other_payee.id), ids)

    def test_no_payees(self):
        self.assertEqual(list_payee_balances(make_user("new@example.com")), {"currency": "GBP", "payees": []})

    def test_only_owing_must_be_boolean(self):
        with self.assertRaises(ToolError):
            list_payee_balances(self.owner, only_owing="yes")


class GetPaymentsTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.sam = Payee.objects.create(user=self.owner, first_name="Sam", last_name="Hill")
        Payment.objects.create(user=self.owner, payee=self.payee, amount=Decimal("80.00"), payment_date=utc(2026, 10, 1, 9), payment_reference="REF-SECRET-1")
        Payment.objects.create(user=self.owner, payee=self.payee, amount=Decimal("45.50"), payment_date=utc(2026, 10, 20, 9))
        Payment.objects.create(user=self.owner, payee=self.sam, amount=Decimal("60.00"), payment_date=utc(2026, 10, 15, 9))
        Payment.objects.create(user=self.owner, payee=self.payee, amount=Decimal("40.00"), payment_date=utc(2026, 11, 1, 9))
        Payment.objects.create(user=self.other, payee=self.other_payee, amount=Decimal("999.00"), payment_date=utc(2026, 10, 15, 9))

    def test_one_payee_in_range_newest_first(self):
        result = get_payments(self.owner, payee_id=str(self.payee.id), start="2026-10-01", end="2026-10-31")
        self.assertEqual(result["payee"], {"id": str(self.payee.id), "name": "Mei Chan"})
        self.assertEqual(result["currency"], "GBP")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["total"], 125.5)
        self.assertEqual([p["amount"] for p in result["payments"]], [45.5, 80.0])
        self.assertEqual(result["payments"][0]["date"], "2026-10-20T10:00+01:00")

    def test_without_payee_covers_all_own_payees(self):
        result = get_payments(self.owner, start="2026-10-01", end="2026-10-31")
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["total"], 185.5)

    def test_never_includes_references_or_other_accounts(self):
        result = get_payments(self.owner)
        self.assertNotIn("REF-SECRET-1", json.dumps(result))
        self.assertNotIn(999.0, [p["amount"] for p in result["payments"]])
        self.assertNotIn(str(self.other_payee.id), {p["payee"]["id"] for p in result["payments"]})

    def test_another_accounts_payee_is_not_found(self):
        with self.assertRaisesMessage(ToolError, "No payee found"):
            get_payments(self.owner, payee_id=str(self.other_payee.id))

    def test_list_is_capped_but_totals_cover_everything(self):
        for _ in range(tools.MAX_PAYMENTS):
            Payment.objects.create(user=self.owner, payee=self.sam, amount=Decimal("1.00"), payment_date=utc(2026, 9, 1))
        result = get_payments(self.owner, payee_id=str(self.sam.id))
        self.assertEqual(result["count"], tools.MAX_PAYMENTS + 1)
        self.assertEqual(len(result["payments"]), tools.MAX_PAYMENTS)
        self.assertEqual(result["total"], 160.0)

    def test_no_payments(self):
        result = get_payments(self.owner, start="2027-01-01")
        self.assertEqual((result["count"], result["total"], result["payments"]), (0, 0.0, []))


class RunToolTests(AssistantTestCase):
    def test_dispatches_by_name(self):
        result = run_tool(self.owner, "find_students", {"name": "Lok"})
        self.assertEqual(result["students"][0]["name"], "Lok Chan")

    def test_results_are_json_serialisable(self):
        make_session(self.owner, self.lok, utc(2026, 11, 2, 16))
        Payment.objects.create(user=self.owner, payee=self.payee, amount=Decimal("10.00"), payment_date=utc(2026, 11, 2))
        for name in TOOLS:
            arguments = {"name": "Chan"} if name == "find_students" else {}
            with self.subTest(tool=name):
                json.dumps(run_tool(self.owner, name, arguments))

    def test_tool_errors_become_error_results(self):
        result = run_tool(self.owner, "count_sessions", {"start": "yesterday"})
        self.assertIn("YYYY-MM-DD", result["error"])

    def test_unknown_tool(self):
        self.assertIn("Unknown tool", run_tool(self.owner, "delete_student", {})["error"])

    def test_unexpected_arguments(self):
        result = run_tool(self.owner, "find_students", {"name": "Lok", "user": "other"})
        self.assertIn("Unexpected arguments", result["error"])

    def test_missing_required_argument(self):
        self.assertIn("Missing required", run_tool(self.owner, "find_students", {})["error"])

    def test_arguments_must_be_an_object(self):
        self.assertIn("JSON object", run_tool(self.owner, "find_students", ["Lok"])["error"])


class ToolSpecTests(TestCase):
    def test_every_tool_has_exactly_one_spec(self):
        self.assertEqual([spec["name"] for spec in TOOL_SPECS], list(TOOLS))

    def test_spec_parameters_match_function_signatures(self):
        for spec in TOOL_SPECS:
            with self.subTest(tool=spec["name"]):
                parameters = inspect.signature(TOOLS[spec["name"]]).parameters
                expected = [name for name in parameters if name != "user"]
                required = [name for name in expected if parameters[name].default is inspect.Parameter.empty]
                self.assertEqual(list(spec["parameters"]["properties"]), expected)
                self.assertEqual(spec["parameters"]["required"], required)
                self.assertFalse(spec["parameters"]["additionalProperties"])
                self.assertTrue(spec["description"])
