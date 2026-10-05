from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended Django User model with phone and role"""
    
    ROLE_CHOICES = [
        ('fan', 'Fan'),
        ('organizer', 'Event Organizer'),
        ('admin', 'Administrator'),
    ]
    
    phone = models.CharField(max_length=15, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='fan')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        db_table = 'users_user'
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"


class Fan(models.Model):
    """Fan-specific profile"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='fan_profile')
    total_bookings = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Fan: {self.user.get_full_name()}"


class Organizer(models.Model):
    """Organizer-specific profile"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='organizer_profile')
    organization_name = models.CharField(max_length=255)
    is_verified = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Organizer: {self.organization_name}"


class Admin(models.Model):
    """Administrator profile"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    permissions = models.CharField(max_length=255, default='full_access')
    
    def __str__(self):
        return f"Admin: {self.user.get_full_name()}"