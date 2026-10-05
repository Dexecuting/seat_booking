from datetime import date, time, timedelta
from decimal import Decimal

from rest_framework.test import APITestCase

from bookings.services import confirm_booking, hold_seat
from users.models import User
from venues.models import Venue, SeatCategory, Seat

from .models import Event


class EventApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venue = Venue.objects.create(name='Kasarani', location='Nairobi', capacity=4)
        vip = SeatCategory.objects.create(venue=cls.venue, name='VIP', price=Decimal('3000'))
        regular = SeatCategory.objects.create(venue=cls.venue, name='Regular', price=Decimal('1000'))
        cls.seats = [
            Seat.objects.create(venue=cls.venue, row_number=r, seat_number=n,
                                category=vip if r == 1 else regular)
            for r in (1, 2) for n in (1, 2)
        ]
        cls.event = Event.objects.create(
            title='Gor Mahia vs AFC Leopards', venue=cls.venue,
            event_date=date.today() + timedelta(days=7), event_time=time(15, 0),
        )
        cls.fan = User.objects.create_user(username='fan', password='x', role='fan')
        cls.organizer = User.objects.create_user(username='org', password='x', role='organizer')

    def event_payload(self, **overrides):
        return {'title': 'Harambee Stars vs Uganda', 'venue': self.venue.id,
                'event_date': str(date.today() + timedelta(days=30)), 'event_time': '16:00',
                **overrides}

    def test_events_are_public(self):
        res = self.client.get('/api/events/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['results'][0]['venue_name'], 'Kasarani')

    def test_event_search(self):
        self.assertEqual(self.client.get('/api/events/?search=leopards').data['count'], 1)
        self.assertEqual(self.client.get('/api/events/?search=nothing').data['count'], 0)

    def test_fan_cannot_create_event(self):
        self.client.force_authenticate(self.fan)
        self.assertEqual(self.client.post('/api/events/', self.event_payload()).status_code, 403)

    def test_anonymous_cannot_create_event(self):
        self.assertEqual(self.client.post('/api/events/', self.event_payload()).status_code, 401)

    def test_organizer_can_create_event(self):
        self.client.force_authenticate(self.organizer)
        res = self.client.post('/api/events/', self.event_payload())
        self.assertEqual(res.status_code, 201, res.data)

    def test_event_date_cannot_be_in_past(self):
        self.client.force_authenticate(self.organizer)
        res = self.client.post('/api/events/', self.event_payload(event_date='2020-01-01'))
        self.assertEqual(res.status_code, 400)

    def test_seat_map_shows_status_per_seat(self):
        hold_seat(self.fan, self.event, self.seats[0])
        confirm_booking(hold_seat(self.fan, self.event, self.seats[1]))

        res = self.client.get(f'/api/events/{self.event.id}/seats/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['summary'], {'available': 2, 'held': 1, 'booked': 1})
        first = res.data['seats'][0]
        self.assertEqual(
            (first['row'], first['number'], first['category'], first['price'], first['status']),
            (1, 1, 'VIP', '3000.00', 'held'),
        )
        self.assertEqual([s['status'] for s in res.data['seats']],
                         ['held', 'booked', 'available', 'available'])

    def test_venues_are_public_with_categories(self):
        res = self.client.get(f'/api/venues/{self.venue.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual({c['name'] for c in res.data['categories']}, {'VIP', 'Regular'})
