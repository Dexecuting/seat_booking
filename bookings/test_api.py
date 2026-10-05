from datetime import date, time, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from events.models import Event
from users.models import User
from venues.models import Venue, SeatCategory, Seat

from .models import Booking


class BookingApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        venue = Venue.objects.create(name='Nyayo', location='Nairobi', capacity=2)
        category = SeatCategory.objects.create(venue=venue, name='Regular', price=Decimal('1000'))
        cls.seat = Seat.objects.create(venue=venue, row_number=1, seat_number=1, category=category)
        cls.seat2 = Seat.objects.create(venue=venue, row_number=1, seat_number=2, category=category)
        cls.event = Event.objects.create(
            title='Match', venue=venue,
            event_date=date.today() + timedelta(days=7), event_time=time(15, 0),
        )
        cls.fan = User.objects.create_user(username='fan', password='x')
        cls.other_fan = User.objects.create_user(username='other', password='x')

    def hold(self, user=None, seat=None):
        self.client.force_authenticate(user or self.fan)
        return self.client.post('/api/bookings/', {'event': self.event.id, 'seat': (seat or self.seat).id})

    def test_must_be_logged_in(self):
        res = self.client.post('/api/bookings/', {'event': self.event.id, 'seat': self.seat.id})
        self.assertEqual(res.status_code, 401)

    def test_hold_seat_for_logged_in_fan(self):
        res = self.hold()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['status'], 'pending')
        self.assertEqual(res.data['price'], '1000.00')
        self.assertGreater(res.data['hold_seconds_remaining'], 0)
        self.assertEqual(Booking.objects.get(pk=res.data['id']).fan, self.fan)

    def test_fan_field_in_request_is_ignored(self):
        self.client.force_authenticate(self.fan)
        res = self.client.post('/api/bookings/',
                               {'event': self.event.id, 'seat': self.seat.id, 'fan': self.other_fan.id})
        self.assertEqual(Booking.objects.get(pk=res.data['id']).fan, self.fan)

    def test_taken_seat_returns_conflict(self):
        self.hold()
        res = self.hold(user=self.other_fan)
        self.assertEqual(res.status_code, 409)
        self.assertIn('taken', res.data['detail'])

    def test_unknown_seat_returns_400(self):
        self.client.force_authenticate(self.fan)
        res = self.client.post('/api/bookings/', {'event': self.event.id, 'seat': 99999})
        self.assertEqual(res.status_code, 400)

    def test_list_only_shows_my_bookings(self):
        self.hold()
        self.hold(user=self.other_fan, seat=self.seat2)
        self.client.force_authenticate(self.fan)
        res = self.client.get('/api/bookings/')
        self.assertEqual(res.data['count'], 1)

    def test_cannot_see_another_fans_booking(self):
        booking_id = self.hold().data['id']
        self.client.force_authenticate(self.other_fan)
        self.assertEqual(self.client.get(f'/api/bookings/{booking_id}/').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/bookings/{booking_id}/').status_code, 404)

    def test_release_hold_frees_seat(self):
        booking_id = self.hold().data['id']
        res = self.client.delete(f'/api/bookings/{booking_id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['status'], 'cancelled')
        self.assertEqual(self.hold(user=self.other_fan).status_code, 201)

    def test_lapsed_hold_shows_as_expired(self):
        booking_id = self.hold().data['id']
        Booking.objects.filter(pk=booking_id).update(hold_expires_at=timezone.now() - timedelta(seconds=1))
        res = self.client.get(f'/api/bookings/{booking_id}/')
        self.assertEqual(res.data['status'], 'expired')
        self.assertIsNone(res.data['hold_seconds_remaining'])
