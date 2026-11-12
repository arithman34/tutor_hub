import uuid

from django.test import Client, TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from billing.models import Payee
from students.models import Student


def make_user(email, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class StudentFormsCsrfTests(TestCase):
    """Regression test: Client() doesn't enforce CSRF, so a template missing
    {{ csrf_token }} can pass every other test while 403ing for real browsers.
    These use a CSRF-enforcing client to catch that."""

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.tutor = make_user("tutor@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")
        login(self.client, self.tutor)

    def _csrf_token(self, get_path):
        self.client.get(get_path)
        return self.client.cookies["csrftoken"].value

    def test_create_form_includes_working_csrf_token(self):
        token = self._csrf_token("/students/new")
        response = self.client.post("/students", {"first_name": "New", "last_name": "Student", "csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)

    def test_update_form_includes_working_csrf_token(self):
        token = self._csrf_token(f"/students/{self.student.id}")
        response = self.client.post(f"/students/{self.student.id}/update", {"first_name": "Sam", "csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)

    def test_toggle_active_form_includes_working_csrf_token(self):
        token = self._csrf_token(f"/students/{self.student.id}")
        response = self.client.post(f"/students/{self.student.id}/toggle-active", {"csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)

    def test_delete_form_includes_working_csrf_token(self):
        token = self._csrf_token(f"/students/{self.student.id}")
        response = self.client.post(f"/students/{self.student.id}/delete", {"csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)


class StudentsListPageTests(TestCase):
    def test_shows_only_own_students(self):
        tutor = make_user("tutor@example.com")
        other = make_user("other@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        Student.objects.create(user=other, first_name="Pat", last_name="Jones")

        login(self.client, tutor)
        response = self.client.get("/students")
        self.assertContains(response, "Sam")
        self.assertNotContains(response, "Pat Jones")

    def test_shows_add_student_link(self):
        login(self.client, make_user("tutor@example.com"))
        response = self.client.get("/students")
        self.assertContains(response, "Add Student")

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/students")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)

    def test_search_filters_by_name(self):
        tutor = make_user("tutor@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        Student.objects.create(user=tutor, first_name="Pat", last_name="Jones")

        login(self.client, tutor)
        response = self.client.get("/students", {"q": "sam"})
        self.assertContains(response, "Sam")
        self.assertNotContains(response, "Pat Jones")


class StudentCreateTests(TestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.other = make_user("other@example.com")
        login(self.client, self.tutor)

    def test_creates_student_owned_by_current_user(self):
        response = self.client.post("/students", {"first_name": "new", "last_name": "student"})
        self.assertRedirects(response, "/students", fetch_redirect_response=False)
        student = Student.objects.get()
        self.assertEqual(student.first_name, "New")
        self.assertEqual(student.user, self.tutor)

    def test_owner_cannot_be_overridden_by_form(self):
        self.client.post("/students", {"first_name": "new", "last_name": "student", "tutor_id": str(self.other.id)})
        self.assertEqual(Student.objects.get().user, self.tutor)

    def test_attaches_own_payee(self):
        payee = Payee.objects.create(user=self.tutor, first_name="Jo", last_name="Payer")
        self.client.post("/students", {"first_name": "new", "last_name": "student", "payee_id": str(payee.id)})
        self.assertEqual(Student.objects.get().payee, payee)

    def test_ignores_another_accounts_payee(self):
        foreign = Payee.objects.create(user=self.other, first_name="Lee", last_name="Other")
        self.client.post("/students", {"first_name": "new", "last_name": "student", "payee_id": str(foreign.id)})
        self.assertIsNone(Student.objects.get().payee)

    def test_new_page_lists_only_own_payees(self):
        Payee.objects.create(user=self.tutor, first_name="Jo", last_name="Payer")
        Payee.objects.create(user=self.other, first_name="Lee", last_name="Other")
        response = self.client.get("/students/new")
        self.assertContains(response, "Jo Payer")
        self.assertNotContains(response, "Lee Other")
        self.assertNotContains(response, "tutor_id")


class StudentDetailTests(TestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.other_tutor = make_user("other@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")

    def test_owner_can_view_detail(self):
        login(self.client, self.tutor)
        response = self.client.get(f"/students/{self.student.id}")
        self.assertContains(response, "Sam Smith")

    def test_detail_offers_only_own_payees(self):
        Payee.objects.create(user=self.tutor, first_name="Jo", last_name="Payer")
        Payee.objects.create(user=self.other_tutor, first_name="Lee", last_name="Other")
        login(self.client, self.tutor)
        response = self.client.get(f"/students/{self.student.id}")
        self.assertContains(response, "Jo Payer")
        self.assertNotContains(response, "Lee Other")

    def test_other_tutor_redirected_away(self):
        login(self.client, self.other_tutor)
        response = self.client.get(f"/students/{self.student.id}")
        self.assertRedirects(response, "/students", fetch_redirect_response=False)
        self.assertNotContains(response, "Sam Smith", status_code=302)

    def test_nonexistent_student_redirects(self):
        login(self.client, self.tutor)
        response = self.client.get(f"/students/{uuid.uuid4()}")
        self.assertRedirects(response, "/students", fetch_redirect_response=False)


class StudentUpdateTests(TestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.other = make_user("other@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")

    def test_owner_can_update(self):
        login(self.client, self.tutor)
        response = self.client.post(f"/students/{self.student.id}/update", {"first_name": "sam", "level": "GCSE"})
        self.assertRedirects(response, f"/students/{self.student.id}", fetch_redirect_response=False)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Sam")
        self.assertEqual(self.student.level, "GCSE")

    def test_update_parses_google_doc_id_from_ilp_url(self):
        login(self.client, self.tutor)
        self.client.post(
            f"/students/{self.student.id}/update",
            {"first_name": "Sam", "ilp_url": "https://docs.google.com/document/d/abc123XYZ/edit"},
        )
        self.student.refresh_from_db()
        self.assertEqual(self.student.google_doc_id, "abc123XYZ")

    def test_cannot_attach_another_accounts_payee(self):
        foreign = Payee.objects.create(user=self.other, first_name="Lee", last_name="Other")
        login(self.client, self.tutor)
        self.client.post(f"/students/{self.student.id}/update", {"first_name": "Sam", "payee_id": str(foreign.id)})
        self.student.refresh_from_db()
        self.assertIsNone(self.student.payee)

    def test_other_account_cannot_update(self):
        login(self.client, self.other)
        response = self.client.post(f"/students/{self.student.id}/update", {"first_name": "changed"})
        self.assertEqual(response.status_code, 404)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Sam")


class StudentToggleActiveTests(TestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith", is_active=True)

    def test_owner_can_toggle(self):
        login(self.client, self.tutor)
        self.client.post(f"/students/{self.student.id}/toggle-active")
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)

    def test_other_account_toggle_is_a_no_op(self):
        login(self.client, make_user("other@example.com"))
        self.client.post(f"/students/{self.student.id}/toggle-active")
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)


class StudentDeleteTests(TestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")

    def test_owner_can_delete(self):
        login(self.client, self.tutor)
        response = self.client.post(f"/students/{self.student.id}/delete")
        self.assertRedirects(response, "/students", fetch_redirect_response=False)
        self.assertFalse(Student.objects.filter(id=self.student.id).exists())

    def test_other_account_cannot_delete(self):
        login(self.client, make_user("other@example.com"))
        self.client.post(f"/students/{self.student.id}/delete")
        self.assertTrue(Student.objects.filter(id=self.student.id).exists())
