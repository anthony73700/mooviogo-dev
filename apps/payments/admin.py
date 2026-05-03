from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["stripe_payment_intent_id", "user", "amount", "currency", "status", "created_at"]
    list_filter = ["status", "currency"]
    search_fields = ["stripe_payment_intent_id", "stripe_charge_id", "user__email"]
    date_hierarchy = "created_at"
    readonly_fields = ["stripe_payment_intent_id", "stripe_charge_id", "metadata"]
