from django.contrib import admin

from .models import GateEntry


@admin.register(GateEntry)
class GateEntryAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'scan_time', 'entry_allowed', 'notes')
    list_filter = ('entry_allowed',)
    search_fields = ('ticket__qr_token',)
    readonly_fields = ('scan_time',)
