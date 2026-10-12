from django.utils import timezone
from rest_framework import serializers

from venues.models import Venue

from .models import Event


class EventSerializer(serializers.ModelSerializer):
    venue = serializers.PrimaryKeyRelatedField(queryset=Venue.objects.all())
    venue_name = serializers.CharField(source='venue.name', read_only=True)
    venue_location = serializers.CharField(source='venue.location', read_only=True)
    price_from = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = ('id', 'title', 'description', 'venue', 'venue_name', 'venue_location',
                  'event_date', 'event_time', 'status', 'price_from')

    def get_price_from(self, event):
        """Cheapest seat category at the venue (annotated by EventViewSet), as a string like '300.00'."""
        price = getattr(event, 'price_from', None)
        return f'{price:.2f}' if price is not None else None

    def validate_venue(self, value):
        # Bookings point at this venue's seats, so the venue is fixed once anyone has booked.
        if self.instance and self.instance.venue_id != value.id and self.instance.bookings.exists():
            raise serializers.ValidationError('The venue cannot be changed after seats have been booked.')
        return value

    def validate_event_date(self, value):
        unchanged = self.instance and self.instance.event_date == value
        if not unchanged and value < timezone.localdate():
            raise serializers.ValidationError('Event date cannot be in the past.')
        return value


class EventSeatSerializer(serializers.Serializer):
    """One seat on an event's seat map, with its availability for that event."""
    id = serializers.IntegerField()
    row = serializers.IntegerField(source='row_number')
    number = serializers.IntegerField(source='seat_number')
    category_id = serializers.IntegerField()
    category = serializers.CharField(source='category.name')
    price = serializers.DecimalField(source='category.price', max_digits=10, decimal_places=2)
    status = serializers.CharField()
