from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "booking_type", "status", "amount", "currency", "created_at"]
    list_filter = ["status", "booking_type"]
    search_fields = ["user__email", "stripe_payment_intent_id"]
    date_hierarchy = "created_at"
