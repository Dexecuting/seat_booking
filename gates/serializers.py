from rest_framework import serializers

from .models import GateEntry


class ScanSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255, trim_whitespace=True)
    event = serializers.IntegerField(required=False,
                                     help_text='Event this gate is admitting; other tickets are rejected.')


def scan_result_data(result):
    """What the scanner screen shows: green/red plus who and where to seat them."""
    data = {'allowed': result.allowed, 'reason': result.reason, 'ticket': None}
    if result.ticket:
        booking = result.ticket.booking
        data['ticket'] = {
            'id': result.ticket.id,
            'holder': booking.fan.get_full_name() or booking.fan.username,
            'event': booking.event.title,
            'row': booking.seat.row_number,
            'seat_number': booking.seat.seat_number,
            'category': booking.seat.category.name,
        }
    return data


class GateEntrySerializer(serializers.ModelSerializer):
    scanned_by = serializers.CharField(source='scanned_by.username', read_only=True, default=None)
    event = serializers.CharField(source='ticket.booking.event.title', read_only=True, default=None)

    class Meta:
        model = GateEntry
        fields = ('id', 'scan_time', 'entry_allowed', 'notes', 'ticket', 'event', 'scanned_by')
        read_only_fields = fields
