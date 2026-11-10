from django.contrib import admin

from .models import Payee, Payment


@admin.register(Payee)
class PayeeAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone_number", "created_at")
    search_fields = ("first_name", "last_name", "email")
    autocomplete_fields = ("user",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("payee", "amount", "payment_date", "payment_reference")
    list_filter = ("payment_date",)
    search_fields = ("payee__first_name", "payee__last_name", "payment_reference")
    autocomplete_fields = ("user", "payee")
    date_hierarchy = "payment_date"
