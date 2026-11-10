from django.test import Client, TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserRole
from billing.models import Payee
from students.models import Student


def make_user(email, role=UserRole.TUTOR, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", role=role, **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class StudentFormsCsrfTests(TestCase):
    """Regression test: Client() doesn't enforce CSRF, so a template missing
    {{ csrf_token }} can pass every other test while 403ing for real browsers.
    These use a CSRF-enforcing client to catch that."""

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.admin = make_user("admin@example.com", UserRole.ADMIN)
        self.tutor = make_user("tutor@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")
        login(self.client, self.admin)

    def _csrf_token(self, get_path):
        self.client.get(get_path)
        return self.client.cookies["csrftoken"].value

    def test_create_form_includes_working_csrf_token(self):
        token = self._csrf_token("/students/new")
        response = self.client.post(
            "/students", {"first_name": "New", "last_name": "Student", "tutor_id": str(self.tutor.id), "csrfmiddlewaretoken": token}
        )
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
    def test_tutor_sees_only_own_students(self):
        tutor = make_user("tutor@example.com")
        other = make_user("other@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        Student.objects.create(user=other, first_name="Pat", last_name="Jones")

        login(self.client, tutor)
        response = self.client.get("/students")
        self.assertContains(response, "Sam")
        self.assertNotContains(response, "Pat")

    def test_admin_sees_add_student_link(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.get("/students")
        self.assertContains(response, "Add Student")

    def test_tutor_does_not_see_add_student_link(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/students")
        self.assertNotContains(response, "Add Student")

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/students")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)

    def test_search_filters_by_name(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        Student.objects.create(user=tutor, first_name="Pat", last_name="Jones")

        login(self.client, admin)
        response = self.client.get("/students", {"q": "sam"})
        self.assertContains(response, "Sam")
        self.assertNotContains(response, "Pat")


class StudentCreateTests(TestCase):
    def test_tutor_cannot_create_student(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.post("/students", {"first_name": "new", "last_name": "student", "tutor_id": str(tutor.id)})
        self.assertEqual(Student.objects.count(), 0)
        self.assertRedirects(response, "/students", fetch_redirect_response=False)

    def test_admin_can_create_student(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        login(self.client, admin)

        response = self.client.post("/students", {"first_name": "new", "last_name": "student", "tutor_id": str(tutor.id)})
        self.assertRedirects(response, "/students", fetch_redirect_response=False)
        student = Student.objects.get()
        self.assertEqual(student.first_name, "New")
        self.assertEqual(student.user_id, tutor.id)

    def test_new_page_redirects_non_admin(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/students/new")
        self.assertRedirects(response, "/students", fetch_redirect_response=False)

    def test_new_page_lists_tutors_and_payees_for_admin(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        Payee.objects.create(user=admin, first_name="Jo", last_name="Payer")
        login(self.client, admin)

        response = self.client.get("/students/new")
        self.assertContains(response, tutor.first_name)
        self.assertContains(response, "Jo Payer")


class StudentDetailTests(TestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.other_tutor = make_user("other@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")

    def test_owner_can_view_detail(self):
        login(self.client, self.tutor)
        response = self.client.get(f"/students/{self.student.id}")
        self.assertContains(response, "Sam Smith")

    def test_other_tutor_redirected_away(self):
        login(self.client, self.other_tutor)
        response = self.client.get(f"/students/{self.student.id}")
        self.assertRedirects(response, "/students", fetch_redirect_response=False)

    def test_nonexistent_student_redirects(self):
        import uuid

        login(self.client, self.tutor)
        response = self.client.get(f"/students/{uuid.uuid4()}")
        self.assertRedirects(response, "/students", fetch_redirect_response=False)


class StudentUpdateTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", UserRole.ADMIN)
        self.tutor = make_user("tutor@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")

    def test_admin_can_update(self):
        login(self.client, self.admin)
        response = self.client.post(f"/students/{self.student.id}/update", {"first_name": "sam", "level": "GCSE"})
        self.assertRedirects(response, f"/students/{self.student.id}", fetch_redirect_response=False)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Sam")
        self.assertEqual(self.student.level, "GCSE")

    def test_update_parses_google_doc_id_from_ilp_url(self):
        login(self.client, self.admin)
        self.client.post(
            f"/students/{self.student.id}/update",
            {"first_name": "Sam", "ilp_url": "https://docs.google.com/document/d/abc123XYZ/edit"},
        )
        self.student.refresh_from_db()
        self.assertEqual(self.student.google_doc_id, "abc123XYZ")

    def test_tutor_cannot_update(self):
        login(self.client, self.tutor)
        response = self.client.post(f"/students/{self.student.id}/update", {"first_name": "changed"})
        self.assertRedirects(response, f"/students/{self.student.id}", fetch_redirect_response=False)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Sam")


class StudentToggleActiveTests(TestCase):
    def test_admin_can_toggle(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        student = Student.objects.create(user=tutor, first_name="Sam", last_name="Smith", is_active=True)

        login(self.client, admin)
        self.client.post(f"/students/{student.id}/toggle-active")
        student.refresh_from_db()
        self.assertFalse(student.is_active)

    def test_tutor_toggle_is_a_no_op(self):
        tutor = make_user("tutor@example.com")
        student = Student.objects.create(user=tutor, first_name="Sam", last_name="Smith", is_active=True)

        login(self.client, tutor)
        self.client.post(f"/students/{student.id}/toggle-active")
        student.refresh_from_db()
        self.assertTrue(student.is_active)


class StudentDeleteTests(TestCase):
    def test_admin_can_delete(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        student = Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")

        login(self.client, admin)
        response = self.client.post(f"/students/{student.id}/delete")
        self.assertRedirects(response, "/students", fetch_redirect_response=False)
        self.assertFalse(Student.objects.filter(id=student.id).exists())

    def test_tutor_cannot_delete(self):
        tutor = make_user("tutor@example.com")
        student = Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")

        login(self.client, tutor)
        self.client.post(f"/students/{student.id}/delete")
        self.assertTrue(Student.objects.filter(id=student.id).exists())
