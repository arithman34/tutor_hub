from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from billing.models import Payee

from .models import Student


def make_user(email):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B")


class StudentListTests(APITestCase):
    def setUp(self):
        self.tutor_a = make_user("tutor-a@example.com")
        self.tutor_b = make_user("tutor-b@example.com")
        self.student_a = Student.objects.create(user=self.tutor_a, first_name="Sam", last_name="Smith")
        self.student_a2 = Student.objects.create(user=self.tutor_a, first_name="Lok", last_name="Chan")
        self.student_b = Student.objects.create(user=self.tutor_b, first_name="Sam", last_name="Jones")
        self.url = reverse("student-list")

    def test_account_sees_only_own_students(self):
        self.client.force_authenticate(self.tutor_a)
        response = self.client.get(self.url)
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.student_a.id), str(self.student_a2.id)})

    def test_search_filters_by_name_within_own_students(self):
        self.client.force_authenticate(self.tutor_a)
        response = self.client.get(self.url, {"q": "sam"})
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.student_a.id)})

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class StudentCreateTests(APITestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.other = make_user("other@example.com")
        self.url = reverse("student-list")

    def test_create_student_for_self_with_capitalised_name(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.post(self.url, {"first_name": "new", "last_name": "student"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["first_name"], "New")
        self.assertEqual(Student.objects.get(id=response.data["id"]).user, self.tutor)

    def test_owner_field_in_payload_is_ignored(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.post(self.url, {"first_name": "new", "last_name": "student", "user": str(self.other.id)})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Student.objects.get(id=response.data["id"]).user, self.tutor)

    def test_can_attach_own_payee(self):
        payee = Payee.objects.create(user=self.tutor, first_name="Jo", last_name="Payer")
        self.client.force_authenticate(self.tutor)
        response = self.client.post(self.url, {"first_name": "new", "last_name": "student", "payee_id": str(payee.id)})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["payee_id"], payee.id)

    def test_cannot_attach_another_accounts_payee(self):
        payee = Payee.objects.create(user=self.other, first_name="Jo", last_name="Payer")
        self.client.force_authenticate(self.tutor)
        response = self.client.post(self.url, {"first_name": "new", "last_name": "student", "payee_id": str(payee.id)})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Student.objects.exists())


class StudentDetailAndMutationTests(APITestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.other_tutor = make_user("other@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")
        self.detail_url = reverse("student-detail", args=[self.student.id])
        self.toggle_url = reverse("student-toggle-active", args=[self.student.id])

    def test_owner_can_retrieve(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_update(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.patch(self.detail_url, {"level": "GCSE"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["level"], "GCSE")

    def test_owner_can_toggle_active(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.post(self.toggle_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

    def test_owner_can_delete(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Student.objects.filter(id=self.student.id).exists())

    def test_other_account_gets_404_for_everything(self):
        self.client.force_authenticate(self.other_tutor)
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(self.detail_url, {"level": "GCSE"}).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(self.toggle_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(self.detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)
        self.assertIsNone(self.student.level)
