from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "address",
            "is_demo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_demo", "created_at", "updated_at"]


class ProfileSerializer(serializers.ModelSerializer):
    """The fields a user may change about themselves.

    Deliberately excludes is_active, is_staff and the AI limit, so a user
    can't grant themselves anything.
    """

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "address"]
        extra_kwargs = {"address": {"required": False, "allow_null": True, "allow_blank": True}}

    def validate_email(self, value):
        value = User.objects.normalize_email(value)
        taken = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_address(self, value):
        return (value or "").strip() or None


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value


class SetupStatusSerializer(serializers.Serializer):
    needed = serializers.BooleanField(help_text="True only while no account exists yet.")


class SetupSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_first_name(self, value):
        return value.strip().title()

    def validate_last_name(self, value):
        return value.strip().title()

    def validate(self, attrs):
        candidate = User(email=attrs["email"], first_name=attrs["first_name"], last_name=attrs["last_name"])
        try:
            password_validation.validate_password(attrs["password"], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs
