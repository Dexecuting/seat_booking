from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'fan', 'event', 'seat', 'status', 'booking_date', 'hold_expires_at')
    list_filter = ('status', 'event')
    search_fields = ('fan__username', 'fan__email', 'event__title')
    list_select_related = ('fan', 'event', 'seat', 'seat__venue')
    raw_id_fields = ('fan', 'seat')
