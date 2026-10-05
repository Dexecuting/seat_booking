from django.db import models
from django.utils import timezone
from datetime import timedelta
from users.models import User
from venues.models import Seat
from events.models import Event


class Booking(models.Model):
    """Seat booking transaction"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    # Bookings in these states occupy the seat for the event.
    ACTIVE_STATUSES = ('pending', 'confirmed')
    
    fan = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE, related_name='bookings')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='bookings')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    booking_date = models.DateTimeField(auto_now_add=True)
    hold_duration_minutes = models.IntegerField(default=10)
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'bookings_booking'
        constraints = [
            # Only one active booking per seat per event; cancelled/expired ones free the seat.
            models.UniqueConstraint(
                fields=['seat', 'event'],
                condition=models.Q(status__in=['pending', 'confirmed']),
                name='unique_active_booking_per_seat_event',
            ),
        ]
    
    def __str__(self):
        return f"Booking: {self.fan.email} - {self.seat}"
    
    def set_hold_timer(self):
        """Set seat hold expiration time"""
        self.hold_expires_at = timezone.now() + timedelta(minutes=self.hold_duration_minutes)
    
    def is_hold_expired(self):
        """Check if hold timer has expired"""
        return timezone.now() > self.hold_expires_at if self.hold_expires_at else False