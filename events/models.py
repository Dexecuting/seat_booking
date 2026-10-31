from django.conf import settings
from django.db import models
from django.db.models import Case, CharField, F, Value, When
from django.utils import timezone
from venues.models import Venue


class EventQuerySet(models.QuerySet):
    def with_live_status(self):
        """Annotate live_status: the database version of Event.current_status, for filtering."""
        now = timezone.localtime()
        return self.annotate(live_status=Case(
            When(status__in=Event.FINAL_STATUSES, then=F('status')),
            When(event_date__lt=now.date(), then=Value('completed')),
            When(event_date=now.date(), event_time__lte=now.time(), then=Value('ongoing')),
            default=F('status'),
            output_field=CharField(),
        ))


class Event(models.Model):
    """Sports event at a venue"""
    
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    FINAL_STATUSES = ('completed', 'cancelled')
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='events')
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='organized_events',
        help_text='Organizer who owns this event. Events without one are managed by administrators.',
    )
    event_date = models.DateField()
    event_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EventQuerySet.as_manager()
    
    class Meta:
        db_table = 'events_event'
    
    def __str__(self):
        return f"{self.title} - {self.event_date}"

    @property
    def current_status(self):
        """The status allowing for the clock: an event is never upcoming once it has kicked off."""
        if self.status in self.FINAL_STATUSES:
            return self.status
        now = timezone.localtime()
        if self.event_date < now.date():
            return 'completed'
        if self.event_date == now.date() and self.event_time <= now.time():
            return 'ongoing'
        return self.status
