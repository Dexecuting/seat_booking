from django.db import models
import secrets
from bookings.models import Booking


class Ticket(models.Model):
    """QR code ticket for venue entry"""
    
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='ticket')
    qr_token = models.CharField(max_length=255, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'tickets_ticket'
    
    def __str__(self):
        return f"Ticket: {self.qr_token[:10]}... ({self.booking.fan.email})"
    
    @staticmethod
    def generate_qr_token():
        """Generate unique QR token"""
        return secrets.token_urlsafe(32)