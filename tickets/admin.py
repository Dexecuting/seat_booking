from django.contrib import admin

from .models import Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'is_used', 'created_at', 'used_at')
    list_filter = ('is_used',)
    search_fields = ('qr_token', 'booking__fan__email')
    readonly_fields = ('qr_token', 'created_at')
    raw_id_fields = ('booking',)
