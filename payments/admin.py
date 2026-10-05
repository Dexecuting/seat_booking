from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'amount', 'phone', 'mpesa_reference', 'status', 'payment_date')
    list_filter = ('status',)
    search_fields = ('mpesa_reference', 'checkout_request_id', 'phone', 'booking__fan__email')
    raw_id_fields = ('booking',)
