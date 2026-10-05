from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'venue', 'event_date', 'event_time', 'status')
    list_filter = ('status', 'venue', 'event_date')
    search_fields = ('title', 'venue__name')
    date_hierarchy = 'event_date'
