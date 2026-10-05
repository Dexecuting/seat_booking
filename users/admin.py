from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, Fan, Organizer, Admin


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'phone', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Seat Booking', {'fields': ('phone', 'role')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Seat Booking', {'fields': ('email', 'phone', 'role')}),
    )


@admin.register(Fan)
class FanAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_bookings', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'user__email')


@admin.register(Organizer)
class OrganizerAdmin(admin.ModelAdmin):
    list_display = ('organization_name', 'user', 'is_verified')
    list_filter = ('is_verified',)
    search_fields = ('organization_name', 'user__username', 'user__email')


@admin.register(Admin)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'permissions')
    search_fields = ('user__username', 'user__email')
