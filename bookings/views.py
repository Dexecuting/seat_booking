from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from .models import Booking
from .serializers import BookingSerializer, HoldSeatSerializer
from .services import BookingError, SeatUnavailable, expire_stale_holds, hold_seat, release_hold


def error_response(exc):
    code = status.HTTP_409_CONFLICT if isinstance(exc, SeatUnavailable) else status.HTTP_400_BAD_REQUEST
    return Response({'detail': str(exc)}, status=code)


class BookingViewSet(mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.DestroyModelMixin,
                     viewsets.GenericViewSet):
    """
    The logged-in user's bookings.

    GET    /api/bookings/                         - my bookings (?status=pending etc.)
    POST   /api/bookings/  {"event": 1, "seat": 5} - hold a seat while paying
    GET    /api/bookings/<id>/                    - one of my bookings
    DELETE /api/bookings/<id>/                    - release a pending hold
    """
    serializer_class = BookingSerializer
    filterset_fields = ['status', 'event']

    def get_queryset(self):
        return (Booking.objects
                .filter(fan=self.request.user)
                .select_related('event__venue', 'seat__category')
                .order_by('-booking_date'))

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # Show lapsed holds as 'expired' rather than 'pending'.
        expire_stale_holds(fan=request.user)

    def create(self, request, *args, **kwargs):
        serializer = HoldSeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = hold_seat(request.user, **serializer.validated_data)
        except BookingError as exc:
            return error_response(exc)
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        try:
            booking = release_hold(self.get_object(), request.user)
        except BookingError as exc:
            return error_response(exc)
        return Response(BookingSerializer(booking).data)
