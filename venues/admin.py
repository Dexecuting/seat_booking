from django.contrib import admin

from .models import Venue, SeatCategory, Seat


class SeatCategoryInline(admin.TabularInline):
    model = SeatCategory
    extra = 0


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'capacity', 'created_at')
    search_fields = ('name', 'location')
    inlines = [SeatCategoryInline]


@admin.register(SeatCategory)
class SeatCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'venue', 'price')
    list_filter = ('venue',)
    search_fields = ('name', 'venue__name')


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ('venue', 'row_number', 'seat_number', 'category')
    list_filter = ('venue', 'category')
    search_fields = ('venue__name',)
    ordering = ('venue', 'row_number', 'seat_number')
    list_select_related = ('venue', 'category')
