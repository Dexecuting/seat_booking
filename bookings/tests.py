from datetime import date, time, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from events.models import Event
from users.models import User
from venues.models import Venue, SeatCategory, Seat

from .models import Booking
from .services import (
    HoldExpired, InvalidBooking, SeatUnavailable,
    confirm_booking, expire_stale_holds, get_seat_statuses, hold_seat, release_hold,
)


class BookingServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venue = Venue.objects.create(name='Test Stadium', location='Nairobi', capacity=3)
        cls.category = SeatCategory.objects.create(venue=cls.venue, name='Regular', price=Decimal('1000'))
        cls.seat1, cls.seat2, cls.seat3 = [
            Seat.objects.create(venue=cls.venue, row_number=1, seat_number=n, category=cls.category)
            for n in (1, 2, 3)
        ]
        cls.event = Event.objects.create(
            title='Match', venue=cls.venue,
            event_date=date.today() + timedelta(days=7), event_time=time(15, 0),
        )
        cls.fan = User.objects.create_user(username='fan1', password='x')
        cls.other_fan = User.objects.create_user(username='fan2', password='x')

    def expire(self, booking):
        """Push a booking's hold timer into the past."""
        booking.hold_expires_at = timezone.now() - timedelta(seconds=1)
        booking.save(update_fields=['hold_expires_at'])

    # hold_seat

    @override_settings(SEAT_HOLD_DURATION_MINUTES=7)
    def test_hold_creates_pending_booking_with_timer(self):
        booking = hold_seat(self.fan, self.event, self.seat1)
        self.assertEqual(booking.status, 'pending')
        self.assertEqual(booking.hold_duration_minutes, 7)
        remaining = booking.hold_expires_at - timezone.now()
        self.assertTrue(timedelta(minutes=6) < remaining <= timedelta(minutes=7))

    def test_cannot_hold_seat_already_held(self):
        hold_seat(self.fan, self.event, self.seat1)
        with self.assertRaises(SeatUnavailable):
            hold_seat(self.other_fan, self.event, self.seat1)

    def test_cannot_hold_seat_already_booked(self):
        confirm_booking(hold_seat(self.fan, self.event, self.seat1))
        with self.assertRaises(SeatUnavailable):
            hold_seat(self.other_fan, self.event, self.seat1)

    def test_can_hold_seat_after_previous_hold_expires(self):
        first = hold_seat(self.fan, self.event, self.seat1)
        self.expire(first)
        second = hold_seat(self.other_fan, self.event, self.seat1)
        first.refresh_from_db()
        self.assertEqual(first.status, 'expired')
        self.assertEqual(second.status, 'pending')

    def test_can_hold_seat_after_previous_hold_released(self):
        release_hold(hold_seat(self.fan, self.event, self.seat1), self.fan)
        self.assertEqual(hold_seat(self.other_fan, self.event, self.seat1).status, 'pending')

    def test_same_seat_can_be_held_for_different_events(self):
        other_event = Event.objects.create(
            title='Other Match', venue=self.venue,
            event_date=date.today() + timedelta(days=14), event_time=time(15, 0),
        )
        hold_seat(self.fan, self.event, self.seat1)
        self.assertEqual(hold_seat(self.other_fan, other_event, self.seat1).status, 'pending')

    def test_cannot_hold_seat_from_another_venue(self):
        other_venue = Venue.objects.create(name='Other', location='Mombasa', capacity=1)
        other_cat = SeatCategory.objects.create(venue=other_venue, name='Regular', price=Decimal('500'))
        foreign_seat = Seat.objects.create(venue=other_venue, row_number=1, seat_number=1, category=other_cat)
        with self.assertRaises(InvalidBooking):
            hold_seat(self.fan, self.event, foreign_seat)

    def test_cannot_hold_seat_for_non_upcoming_event(self):
        self.event.status = 'completed'
        self.event.save()
        with self.assertRaises(InvalidBooking):
            hold_seat(self.fan, self.event, self.seat1)

    # release_hold

    def test_cannot_release_another_fans_hold(self):
        booking = hold_seat(self.fan, self.event, self.seat1)
        with self.assertRaises(InvalidBooking):
            release_hold(booking, self.other_fan)

    def test_cannot_release_confirmed_booking(self):
        booking = confirm_booking(hold_seat(self.fan, self.event, self.seat1))
        with self.assertRaises(InvalidBooking):
            release_hold(booking, self.fan)

    # confirm_booking

    def test_confirm_pending_booking(self):
        booking = confirm_booking(hold_seat(self.fan, self.event, self.seat1))
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'confirmed')

    def test_confirm_is_idempotent(self):
        booking = hold_seat(self.fan, self.event, self.seat1)
        confirm_booking(booking)
        self.assertEqual(confirm_booking(booking).status, 'confirmed')

    def test_confirm_expired_hold_fails_and_marks_expired(self):
        booking = hold_seat(self.fan, self.event, self.seat1)
        self.expire(booking)
        with self.assertRaises(HoldExpired):
            confirm_booking(booking)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'expired')

    def test_confirm_released_hold_fails(self):
        booking = release_hold(hold_seat(self.fan, self.event, self.seat1), self.fan)
        with self.assertRaises(HoldExpired):
            confirm_booking(booking)

    # expire_stale_holds / get_seat_statuses

    def test_expire_stale_holds_only_touches_lapsed_pending(self):
        stale = hold_seat(self.fan, self.event, self.seat1)
        self.expire(stale)
        fresh = hold_seat(self.fan, self.event, self.seat2)
        confirmed = confirm_booking(hold_seat(self.fan, self.event, self.seat3))

        self.assertEqual(expire_stale_holds(), 1)
        for b in (stale, fresh, confirmed):
            b.refresh_from_db()
        self.assertEqual((stale.status, fresh.status, confirmed.status), ('expired', 'pending', 'confirmed'))

    def test_seat_statuses(self):
        hold_seat(self.fan, self.event, self.seat1)
        confirm_booking(hold_seat(self.fan, self.event, self.seat2))
        self.assertEqual(get_seat_statuses(self.event), {
            self.seat1.id: 'held',
            self.seat2.id: 'booked',
            self.seat3.id: 'available',
        })

    def test_seat_statuses_treat_lapsed_hold_as_available(self):
        self.expire(hold_seat(self.fan, self.event, self.seat1))
        self.assertEqual(get_seat_statuses(self.event)[self.seat1.id], 'available')
