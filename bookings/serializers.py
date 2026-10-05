from django.utils import timezone
from rest_framework import serializers

from events.models import Event
from venues.models import Seat

from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='event.title', read_only=True)
    event_date = serializers.DateField(source='event.event_date', read_only=True)
    event_time = serializers.TimeField(source='event.event_time', read_only=True)
    venue = serializers.CharField(source='event.venue.name', read_only=True)
    row = serializers.IntegerField(source='seat.row_number', read_only=True)
    seat_number = serializers.IntegerField(source='seat.seat_number', read_only=True)
    category = serializers.CharField(source='seat.category.name', read_only=True)
    price = serializers.DecimalField(source='seat.category.price', max_digits=10,
                                     decimal_places=2, read_only=True)
    hold_seconds_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = ('id', 'status', 'event', 'event_title', 'event_date', 'event_time', 'venue',
                  'seat', 'row', 'seat_number', 'category', 'price',
                  'booking_date', 'hold_expires_at', 'hold_seconds_remaining')
        read_only_fields = fields

    def get_hold_seconds_remaining(self, booking):
        """Countdown for the payment page; null unless the seat is currently held."""
        if booking.status != 'pending' or not booking.hold_expires_at:
            return None
        return max(0, int((booking.hold_expires_at - timezone.now()).total_seconds()))


class HoldSeatSerializer(serializers.Serializer):
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.select_related('venue'))
    seat = serializers.PrimaryKeyRelatedField(queryset=Seat.objects.all())
