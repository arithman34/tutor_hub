import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    address = models.CharField(max_length=255, null=True, blank=True)
    assistant_daily_limit = models.PositiveIntegerField(
        "TutorHub AI daily limit",
        null=True,
        blank=True,
        default=1,
        help_text="Questions this account can ask TutorHub AI per day (UK time). Leave blank for unlimited.",
    )
    is_demo = models.BooleanField(
        "demo account",
        default=False,
        help_text="The shared, read-only account behind the homepage's Try the demo button. See accounts/demo.py.",
    )
    demo_seeded_at = models.DateTimeField(
        null=True, blank=True, editable=False, help_text="When the demo account's made-up records were last regenerated."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.email
