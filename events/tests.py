from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APITestCase

from bookings.services import InvalidBooking, confirm_booking, hold_seat
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


class EventOwnershipTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venue = Venue.objects.create(name='Kasarani', location='Nairobi', capacity=1)
        cls.other_venue = Venue.objects.create(name='Nyayo', location='Nairobi', capacity=1)
        category = SeatCategory.objects.create(venue=cls.venue, name='Regular', price=Decimal('1000'))
        cls.seat = Seat.objects.create(venue=cls.venue, row_number=1, seat_number=1, category=category)
        cls.owner = User.objects.create_user(username='owner', password='x', role='organizer')
        cls.rival = User.objects.create_user(username='rival', password='x', role='organizer')
        cls.admin = User.objects.create_user(username='boss', password='x', role='admin')
        cls.fan = User.objects.create_user(username='fan', password='x')

    def create_event(self, user, **overrides):
        self.client.force_authenticate(user)
        return self.client.post('/api/events/', {
            'title': 'Owner match', 'venue': self.venue.id,
            'event_date': str(date.today() + timedelta(days=10)), 'event_time': '15:00', **overrides})

    def test_creator_becomes_organizer(self):
        res = self.create_event(self.owner)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Event.objects.get(pk=res.data['id']).organizer, self.owner)

    def test_organizer_field_in_request_is_ignored(self):
        res = self.create_event(self.owner, organizer=self.rival.id)
        self.assertEqual(Event.objects.get(pk=res.data['id']).organizer, self.owner)

    def test_owner_can_edit(self):
        event_id = self.create_event(self.owner).data['id']
        res = self.client.patch(f'/api/events/{event_id}/', {'title': 'Renamed'})
        self.assertEqual(res.status_code, 200)

    def test_other_organizer_cannot_edit_or_delete(self):
        event_id = self.create_event(self.owner).data['id']
        self.client.force_authenticate(self.rival)
        self.assertEqual(self.client.patch(f'/api/events/{event_id}/', {'title': 'Hijacked'}).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/events/{event_id}/').status_code, 403)
        self.assertEqual(Event.objects.get(pk=event_id).title, 'Owner match')

    def test_admin_can_edit_any_event(self):
        event_id = self.create_event(self.owner).data['id']
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(f'/api/events/{event_id}/', {'status': 'cancelled'}).status_code, 200)

    def test_mine_lists_only_own_events(self):
        self.create_event(self.owner, title='Mine')
        self.create_event(self.rival, title='Theirs')
        self.client.force_authenticate(self.owner)
        self.assertEqual([e['title'] for e in self.client.get('/api/events/?mine=true').data['results']], ['Mine'])
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/events/?mine=true').data['count'], 2)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/events/?mine=true').data['count'], 0)
        self.assertEqual(self.client.get('/api/events/').data['count'], 2)  # public list unchanged

    def test_venue_locked_and_delete_blocked_once_booked(self):
        event_id = self.create_event(self.owner).data['id']
        hold_seat(self.fan, Event.objects.get(pk=event_id), self.seat)
        self.client.force_authenticate(self.owner)
        res = self.client.patch(f'/api/events/{event_id}/', {'venue': self.other_venue.id})
        self.assertEqual(res.status_code, 400)
        self.assertIn('venue', res.data)
        res = self.client.delete(f'/api/events/{event_id}/')
        self.assertEqual(res.status_code, 400)
        self.assertTrue(Event.objects.filter(pk=event_id).exists())

    def test_unbooked_event_can_be_deleted(self):
        event_id = self.create_event(self.owner).data['id']
        self.assertEqual(self.client.delete(f'/api/events/{event_id}/').status_code, 204)

    def test_only_admins_change_venues(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.patch(f'/api/venues/{self.venue.id}/', {'name': 'X'}).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(f'/api/venues/{self.venue.id}/', {'name': 'Kasarani Stadium'}).status_code, 200)


class EventDateTests(APITestCase):
    """The clock is fixed at noon so "today before/after kick-off" is exact."""

    @classmethod
    def setUpTestData(cls):
        cls.now = timezone.make_aware(datetime(2026, 6, 15, 12, 0))
        cls.venue = Venue.objects.create(name='Kasarani', location='Nairobi', capacity=1)
        category = SeatCategory.objects.create(venue=cls.venue, name='Regular', price=Decimal('1000'))
        cls.seat = Seat.objects.create(venue=cls.venue, row_number=1, seat_number=1, category=category)
        today = cls.now.date()
        day = timedelta(days=1)
        cls.events = {title: Event.objects.create(title=title, venue=cls.venue, event_date=when,
                                                  event_time=kickoff, status=status)
                      for title, when, kickoff, status in (
                          ('Tomorrow', today + day, time(9, 0), 'upcoming'),
                          ('Tonight', today, time(18, 0), 'upcoming'),
                          ('This morning', today, time(9, 0), 'upcoming'),
                          ('Overdue', today - day, time(18, 0), 'upcoming'),
                          ('Finished', today + day, time(9, 0), 'completed'),
                          ('Called off', today - day, time(9, 0), 'cancelled'),
                      )}
        cls.fan = User.objects.create_user(username='fan', password='x', role='fan')
        cls.organizer = User.objects.create_user(username='org', password='x', role='organizer')
        cls.gate = User.objects.create_user(username='gate', password='x', role='gate_staff')

    def setUp(self):
        patcher = patch('django.utils.timezone.now', return_value=self.now)
        patcher.start()
        self.addCleanup(patcher.stop)

    def titles(self, url):
        return {e['title'] for e in self.client.get(url).data['results']}

    def test_status_filter_uses_the_date(self):
        self.client.force_authenticate(self.organizer)
        self.assertEqual(self.titles('/api/events/?status=upcoming'), {'Tomorrow', 'Tonight'})
        self.assertEqual(self.titles('/api/events/?status=ongoing'), {'This morning'})
        self.assertEqual(self.titles('/api/events/?status=completed'), {'Overdue', 'Finished'})
        self.assertEqual(self.titles('/api/events/?status=cancelled'), {'Called off'})
        self.assertEqual(len(self.titles('/api/events/')), 6)

    def test_python_and_database_rules_agree(self):
        for event in Event.objects.with_live_status():
            self.assertEqual(event.live_status, event.current_status, event.title)

    def test_fans_and_visitors_only_list_upcoming(self):
        for user in (None, self.fan):
            self.client.force_authenticate(user)
            self.assertEqual(self.titles('/api/events/'), {'Tomorrow', 'Tonight'})
            self.assertEqual(self.titles('/api/events/?status=completed'), {'Tomorrow', 'Tonight'})

    def test_fan_cannot_open_past_event(self):
        self.client.force_authenticate(self.fan)
        past = self.events['Overdue'].id
        self.assertEqual(self.client.get(f'/api/events/{past}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/events/{past}/seats/').status_code, 404)

    def test_ticket_holder_can_still_open_their_past_event(self):
        booking = hold_seat(self.fan, self.events['Tonight'], self.seat)
        confirm_booking(booking)
        Event.objects.filter(pk=booking.event_id).update(event_date=self.now.date() - timedelta(days=2))
        self.client.force_authenticate(self.fan)
        self.assertEqual(self.client.get(f'/api/events/{booking.event_id}/').status_code, 200)
        self.assertNotIn('Tonight', self.titles('/api/events/'))

    def test_gate_staff_see_today_after_kick_off(self):
        self.client.force_authenticate(self.gate)
        self.assertEqual(self.titles(f'/api/events/?event_date={self.now.date()}'), {'Tonight', 'This morning'})

    def test_bookings_close_at_kick_off(self):
        for title in ('This morning', 'Overdue'):
            with self.assertRaises(InvalidBooking):
                hold_seat(self.fan, self.events[title], self.seat)
        self.assertEqual(hold_seat(self.fan, self.events['Tonight'], self.seat).status, 'pending')


class AssetVersionTests(APITestCase):
    def test_pages_stamp_script_and_style_urls(self):
        with self.settings(DEBUG=True):
            html = self.client.get('/events/').content.decode()
        self.assertRegex(html, r'js/api\.js\?v=\d+"')
        self.assertRegex(html, r'css/style\.css\?v=\d+"')
