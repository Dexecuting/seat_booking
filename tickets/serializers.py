from rest_framework import serializers

from .models import Ticket
from .qr_generator import qr_data_uri


class TicketSerializer(serializers.ModelSerializer):
    booking = serializers.IntegerField(source='booking.id', read_only=True)
    event = serializers.IntegerField(source='booking.event.id', read_only=True)
    event_title = serializers.CharField(source='booking.event.title', read_only=True)
    event_date = serializers.DateField(source='booking.event.event_date', read_only=True)
    event_time = serializers.TimeField(source='booking.event.event_time', read_only=True)
    venue = serializers.CharField(source='booking.event.venue.name', read_only=True)
    row = serializers.IntegerField(source='booking.seat.row_number', read_only=True)
    seat_number = serializers.IntegerField(source='booking.seat.seat_number', read_only=True)
    category = serializers.CharField(source='booking.seat.category.name', read_only=True)

    class Meta:
        model = Ticket
        fields = ('id', 'booking', 'event', 'event_title', 'event_date', 'event_time', 'venue',
                  'row', 'seat_number', 'category', 'is_used', 'used_at', 'created_at')
        read_only_fields = fields


class TicketDetailSerializer(TicketSerializer):
    """Includes the QR code image (as a data URI) - only on the detail view, not the list."""
    qr_code = serializers.SerializerMethodField()

    class Meta(TicketSerializer.Meta):
        fields = TicketSerializer.Meta.fields + ('qr_code',)
        read_only_fields = fields

    def get_qr_code(self, ticket):
        return qr_data_uri(ticket.qr_token)
