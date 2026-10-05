"""
Seat hold/release logic.

A seat is unavailable for an event while it has an active (pending or confirmed)
booking. Double-booking is prevented by the `unique_active_booking_per_seat_event`
database constraint, so two fans racing for the same seat cannot both succeed:
the loser's insert raises IntegrityError, which is reported as SeatUnavailable.
"""
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Booking


class BookingError(Exception):
    """Base class for booking failures that should be shown to the user."""


class SeatUnavailable(BookingError):
    pass


class InvalidBooking(BookingError):
    pass


class HoldExpired(BookingError):
    pass


def expire_stale_holds(**filters):
    """Mark pending bookings whose hold timer has run out as expired. Returns the count."""
    return Booking.objects.filter(
        status='pending',
        hold_expires_at__lte=timezone.now(),
        **filters,
    ).update(status='expired')


def get_seat_statuses(event):
    """
    Return {seat_id: 'available' | 'held' | 'booked'} for every seat at the event's venue.
    Used to colour the seat map.
    """
    expire_stale_holds(event=event)
    statuses = {seat_id: 'available' for seat_id in event.venue.seats.values_list('id', flat=True)}
    active = Booking.objects.filter(event=event, status__in=Booking.ACTIVE_STATUSES)
    for seat_id, status in active.values_list('seat_id', 'status'):
        statuses[seat_id] = 'booked' if status == 'confirmed' else 'held'
    return statuses


def hold_seat(fan, event, seat):
    """
    Place a temporary hold on a seat for the fan while they pay.
    Raises InvalidBooking or SeatUnavailable.
    """
    if event.status != 'upcoming':
        raise InvalidBooking('Bookings are only open for upcoming events.')
    if seat.venue_id != event.venue_id:
        raise InvalidBooking('This seat is not at the venue for this event.')

    # Free the seat if an earlier hold on it has lapsed.
    expire_stale_holds(event=event, seat=seat)

    booking = Booking(
        fan=fan,
        event=event,
        seat=seat,
        status='pending',
        hold_duration_minutes=settings.SEAT_HOLD_DURATION_MINUTES,
    )
    booking.set_hold_timer()
    try:
        with transaction.atomic():
            booking.save()
    except IntegrityError:
        raise SeatUnavailable('This seat has already been taken.')
    return booking


def release_hold(booking, fan):
    """Let a fan cancel their own pending hold (e.g. they changed seat or abandoned payment)."""
    if booking.fan_id != fan.id:
        raise InvalidBooking('You can only release your own bookings.')
    if booking.status != 'pending':
        raise InvalidBooking(f'Cannot release a {booking.status} booking.')
    booking.status = 'cancelled'
    booking.save(update_fields=['status'])
    return booking


def confirm_booking(booking):
    """
    Confirm a held seat once payment succeeds (called from the M-Pesa callback).
    Locks the row so a concurrent expiry/cancel can't interleave with confirmation.
    Raises HoldExpired if the hold lapsed or was released before payment arrived.
    """
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        if booking.status == 'pending':
            booking.status = 'expired' if booking.is_hold_expired() else 'confirmed'
            booking.save(update_fields=['status'])
    # Raised outside the atomic block so the 'expired' status change is not rolled back.
    if booking.status != 'confirmed':
        raise HoldExpired(f'Booking is {booking.status}; the seat hold ended before payment completed.')
    return booking
