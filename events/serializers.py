from django.utils import timezone
from rest_framework import serializers

from venues.models import Venue

from .models import Event


class EventSerializer(serializers.ModelSerializer):
    venue = serializers.PrimaryKeyRelatedField(queryset=Venue.objects.all())
    venue_name = serializers.CharField(source='venue.name', read_only=True)
    venue_location = serializers.CharField(source='venue.location', read_only=True)

    class Meta:
        model = Event
        fields = ('id', 'title', 'description', 'venue', 'venue_name', 'venue_location',
                  'event_date', 'event_time', 'status')

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
