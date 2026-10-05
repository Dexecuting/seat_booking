from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'amount', 'mpesa_reference', 'status', 'payment_date')
    list_filter = ('status',)
    search_fields = ('mpesa_reference', 'booking__fan__email')
    raw_id_fields = ('booking',)
