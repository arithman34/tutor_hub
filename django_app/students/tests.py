from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserRole

from .models import Student


def make_user(email, role=UserRole.TUTOR):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", role=role)


class StudentListTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", UserRole.ADMIN)
        self.tutor_a = make_user("tutor-a@example.com")
        self.tutor_b = make_user("tutor-b@example.com")
        self.student_a = Student.objects.create(user=self.tutor_a, first_name="Sam", last_name="Smith")
        self.student_b = Student.objects.create(user=self.tutor_b, first_name="Pat", last_name="Jones")
        self.url = reverse("student-list")

    def test_tutor_sees_only_own_students(self):
        self.client.force_authenticate(self.tutor_a)
        response = self.client.get(self.url)
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.student_a.id)})

    def test_admin_sees_all_students(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.url)
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.student_a.id), str(self.student_b.id)})

    def test_search_filters_by_name(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.url, {"q": "sam"})
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.student_a.id)})

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class StudentCreateTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", UserRole.ADMIN)
        self.tutor = make_user("tutor@example.com")
        self.url = reverse("student-list")

    def test_tutor_cannot_create_student(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.post(self.url, {"first_name": "new", "last_name": "student"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_student_for_self(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, {"first_name": "new", "last_name": "student"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["first_name"], "New")  # capitalised
        self.assertEqual(response.data["tutor_id"], str(self.admin.id))

    def test_admin_can_create_student_for_another_tutor(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, {"first_name": "new", "last_name": "student", "tutor_id": str(self.tutor.id)})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["tutor_id"], str(self.tutor.id))


class StudentDetailAndMutationTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", UserRole.ADMIN)
        self.tutor = make_user("tutor@example.com")
        self.other_tutor = make_user("other@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")
        self.detail_url = reverse("student-detail", args=[self.student.id])

    def test_owner_can_retrieve(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_tutor_gets_404(self):
        self.client.force_authenticate(self.other_tutor)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tutor_cannot_update_own_student(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.patch(self.detail_url, {"level": "GCSE"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update_student(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(self.detail_url, {"level": "GCSE"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["level"], "GCSE")

    def test_tutor_cannot_toggle_active(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.post(reverse("student-toggle-active", args=[self.student.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_toggle_active(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(reverse("student-toggle-active", args=[self.student.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

    def test_admin_can_delete_student(self):
        self.client.force_authenticate(self.admin)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Student.objects.filter(id=self.student.id).exists())

    def test_tutor_cannot_delete_student(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
