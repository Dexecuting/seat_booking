from django.contrib import admin

from .models import GateEntry


@admin.register(GateEntry)
class GateEntryAdmin(admin.ModelAdmin):
    list_display = ('scan_time', 'entry_allowed', 'ticket', 'scanned_by', 'notes')
    list_filter = ('entry_allowed', 'ticket__booking__event')
    search_fields = ('scanned_token', 'ticket__qr_token', 'notes')
    readonly_fields = ('scan_time',)
    raw_id_fields = ('ticket', 'scanned_by')
