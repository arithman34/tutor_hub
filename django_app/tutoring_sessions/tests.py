from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserRole
from students.models import Student

from .models import Session


def make_user(email, role=UserRole.TUTOR):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", role=role)


class SessionModelTests(APITestCase):
    def test_minutes_computed_from_start_and_end(self):
        tutor = make_user("tutor@example.com")
        student = Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        now = timezone.now()
        session = Session.objects.create(
            user=tutor,
            student=student,
            session_date=now,
            session_start_time=now,
            session_end_time=now + timedelta(minutes=45),
        )
        self.assertEqual(session.minutes, 45)


class SessionCreateTests(APITestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")
        self.url = reverse("session-list")
        self.now = timezone.now()

    def _payload(self, **overrides):
        payload = {
            "student": str(self.student.id),
            "session_date": self.now.isoformat(),
            "session_start_time": self.now.isoformat(),
            "session_end_time": (self.now + timedelta(minutes=30)).isoformat(),
        }
        payload.update(overrides)
        return payload

    def test_authenticated_user_creates_session_for_self(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.post(self.url, self._payload())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Session.objects.get().user, self.tutor)

    def test_end_before_start_is_rejected(self):
        self.client.force_authenticate(self.tutor)
        bad_payload = self._payload(session_end_time=(self.now - timedelta(minutes=5)).isoformat())
        response = self.client.post(self.url, bad_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_create(self):
        response = self.client.post(self.url, self._payload())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SessionAccessTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", UserRole.ADMIN)
        self.tutor = make_user("tutor@example.com")
        self.other_tutor = make_user("other@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")
        now = timezone.now()
        self.session = Session.objects.create(
            user=self.tutor,
            student=self.student,
            session_date=now,
            session_start_time=now,
            session_end_time=now + timedelta(minutes=30),
        )
        self.detail_url = reverse("session-detail", args=[self.session.id])

    def test_owner_can_retrieve(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_retrieve(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_tutor_gets_404(self):
        self.client.force_authenticate(self.other_tutor)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_update(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.patch(self.detail_url, {"work_covered": "fractions"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["work_covered"], "fractions")

    def test_other_tutor_cannot_update(self):
        self.client.force_authenticate(self.other_tutor)
        response = self.client.patch(self.detail_url, {"work_covered": "fractions"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_delete(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_list_filters_by_owner_unless_admin(self):
        self.client.force_authenticate(self.other_tutor)
        response = self.client.get(reverse("session-list"))
        self.assertEqual(response.data["count"], 0)

        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("session-list"))
        self.assertEqual(response.data["count"], 1)
