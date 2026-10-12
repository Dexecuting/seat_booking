from collections import Counter

from django.db.models import Min

from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response

from bookings.services import get_seat_statuses
from users.permissions import IsEventOwnerOrReadOnly, IsOrganizerOrReadOnly, is_admin

from .models import Event
from .serializers import EventSeatSerializer, EventSerializer


class EventViewSet(viewsets.ModelViewSet):
    """
    /api/events/ - public list/detail. Organizers create events (they become the event's
    organizer) and can change only their own; admins can change any.
    Filter with ?status=upcoming&venue=1, search with ?search=gor,
    ?mine=true for the events the logged-in organizer manages (all events for admins).
    """
    queryset = (Event.objects.select_related('venue')
                .annotate(price_from=Min('venue__categories__price'))
                .order_by('event_date', 'event_time'))
    serializer_class = EventSerializer
    permission_classes = [IsOrganizerOrReadOnly, IsEventOwnerOrReadOnly]
    filterset_fields = ['status', 'venue', 'event_date']
    search_fields = ['title', 'venue__name']
    ordering_fields = ['event_date', 'title']

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('mine') in ('1', 'true'):
            user = self.request.user
            if not user.is_authenticated:
                return queryset.none()
            if not is_admin(user):
                queryset = queryset.filter(organizer=user)
        return queryset

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)

    def perform_destroy(self, instance):
        if instance.bookings.exists():
            raise ValidationError('This event already has bookings. Set its status to Cancelled instead.')
        instance.delete()

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
