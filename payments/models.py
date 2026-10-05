from django.db import models
from bookings.models import Booking


class Payment(models.Model):
    """M-Pesa STK Push payment attempt. A booking can have several (e.g. fan cancelled the first prompt)."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        # Money was received but the seat hold had already lapsed - must be refunded manually.
        ('refund_due', 'Refund Due'),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone = models.CharField(max_length=15, blank=True)
    checkout_request_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    mpesa_reference = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_code = models.CharField(max_length=20, blank=True)
    result_desc = models.CharField(max_length=255, blank=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payments_payment'

    def __str__(self):
        return f"Payment: {self.booking.id} - {self.amount} ({self.status})"
