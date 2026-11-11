"""Every business row (students, sessions, payees, payments) belongs to one
account via its `user` foreign key, and an account only ever sees its own
rows. These helpers keep that rule in one place for the API layer."""

from rest_framework import serializers


class OwnedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """A PK field that only accepts objects owned by the requesting user.

    Without this, a serializer would accept any existing id, letting one
    account attach its rows to another account's student or payee.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return queryset.none()
        return queryset.filter(user=request.user)


class OwnedQuerysetMixin:
    """For DRF viewsets: scope every query to the requesting user and stamp
    new rows with them."""

    model = None

    def get_queryset(self):
        return self.model.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
