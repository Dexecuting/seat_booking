from collections import Counter

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from bookings.services import get_seat_statuses
from users.permissions import IsOrganizerOrReadOnly

from .models import Event
from .serializers import EventSeatSerializer, EventSerializer


class EventViewSet(viewsets.ModelViewSet):
    """
    /api/events/ - public list/detail; organizers can create and edit.
    Filter with ?status=upcoming&venue=1, search with ?search=gor.
    """
    queryset = Event.objects.select_related('venue').order_by('event_date', 'event_time')
    serializer_class = EventSerializer
    permission_classes = [IsOrganizerOrReadOnly]
    filterset_fields = ['status', 'venue']
    search_fields = ['title', 'venue__name']
    ordering_fields = ['event_date', 'title']

    @action(detail=True, methods=['get'])
    def seats(self, request, pk=None):
        """
        GET /api/events/<id>/seats/ - every seat at the venue with its status for this event
        ('available', 'held' or 'booked'). Drives the SVG seat map; not paginated.
        """
        event = self.get_object()
        statuses = get_seat_statuses(event)
        seats = event.venue.seats.select_related('category').order_by('row_number', 'seat_number')
        for seat in seats:
            seat.status = statuses[seat.id]
        counts = Counter(statuses.values())
        return Response({
            'event': event.id,
            'summary': {s: counts[s] for s in ('available', 'held', 'booked')},
            'seats': EventSeatSerializer(seats, many=True).data,
        })
