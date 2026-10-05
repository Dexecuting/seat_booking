from django.db import models
from venues.models import Venue


class Event(models.Model):
    """Sports event at a venue"""
    
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='events')
    event_date = models.DateField()
    event_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'events_event'
    
    def __str__(self):
        return f"{self.title} - {self.event_date}"