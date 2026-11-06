import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class UserRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    TUTOR = "tutor", "Tutor"
    ADMIN_TUTOR = "admin_tutor", "Admin + Tutor"


class PayoutType(models.TextChoices):
    PERCENTAGE = "percentage", "Percentage"
    HOURLY = "hourly", "Hourly"


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=UserRole.choices)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    address = models.CharField(max_length=255, null=True, blank=True)
    payout_type = models.CharField(max_length=20, choices=PayoutType.choices, null=True, blank=True)
    payout_percentage = models.FloatField(null=True, blank=True)
    payout_hourly_rate = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "role"]

    class Meta:
        db_table = "users"
        constraints = [
            models.UniqueConstraint(
                fields=["role"],
                condition=models.Q(role=UserRole.ADMIN),
                name="one_admin",
            )
        ]

    def __str__(self):
        return self.email

    @property
    def is_admin(self):
        return self.role in (UserRole.ADMIN, UserRole.ADMIN_TUTOR)

    @property
    def is_tutor(self):
        return self.role in (UserRole.TUTOR, UserRole.ADMIN_TUTOR)
