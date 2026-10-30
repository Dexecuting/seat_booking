import io
from collections import Counter
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.management import call_command
from rest_framework.test import APITestCase

from bookings.services import hold_seat
from events.models import Event
from users.models import User

from .management.commands.seed_nyayo_court import VENUE_NAME, seat_plan
from .models import Seat, SeatCategory, Venue


class NyayoSeatPlanTests(APITestCase):
    def test_plan_matches_the_surveyed_court(self):
        plan = list(seat_plan())
        self.assertEqual(len(plan), 912)
        self.assertEqual(Counter(item[3] for item in plan), {'Standard': 654, 'Front row': 150, 'Foldable': 108})

    def test_each_photo_is_used_once_except_the_shared_one(self):
        positions = [item[6] for item in seat_plan()]
        self.assertEqual(sorted(set(range(2, 914)) - set(positions)), [643])  # the dropped retake
        self.assertEqual([p for p, n in Counter(positions).items() if n > 1], [517])  # shared by one seat

    def test_every_seat_has_its_own_photo_file_name(self):
        names = [item[7] for item in seat_plan()]
        self.assertEqual(len(names), len(set(names)))

    def test_foldable_block_sizes(self):
        counts = Counter((item[1], item[4]) for item in seat_plan() if item[3] == 'Foldable')
        self.assertEqual(counts[('Foldable green', 1)], 6)
        self.assertEqual(counts[('Foldable red', 1)], 10)
        self.assertEqual(counts[('Foldable red', 5)], 8)
        self.assertEqual(counts[('Foldable black', 5)], 6)


class NyayoVenueTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_nyayo_court', stdout=io.StringIO())
        cls.venue = Venue.objects.get(name=VENUE_NAME)
        cls.event = Event.objects.get(venue=cls.venue)

    def test_prices(self):
        prices = dict(self.venue.categories.values_list('name', 'price'))
        self.assertEqual(prices, {'Front row': Decimal('350.00'), 'Foldable': Decimal('250.00'),
                                  'Standard': Decimal('100.00')})

    def test_seeding_twice_changes_nothing(self):
        call_command('seed_nyayo_court', stdout=io.StringIO())
        self.assertEqual(Seat.objects.filter(venue=self.venue).count(), 912)
        self.assertEqual(Venue.objects.filter(name=VENUE_NAME).count(), 1)

    def test_seat_map_api_returns_layout_and_photo(self):
        data = self.client.get(f'/api/events/{self.event.id}/seats/').data
        self.assertEqual(data['summary']['available'], 912)
        seat = next(s for s in data['seats'] if s['section'] == 'Foldable red' and s['row'] == 2 and s['number'] == 3)
        self.assertEqual((seat['stand'], seat['section_order'], seat['category'], seat['price']),
                         ('second', 3, 'Foldable', '250.00'))
        self.assertIn('venues/nyayo-handball/foldable-red-r2-s003.webp', seat['view_photo'])

    def test_same_row_and_number_in_two_sections_are_different_seats(self):
        fan = User.objects.create_user(username='fan', password='x')
        for section in ('Foldable green', 'Foldable black'):
            seat = Seat.objects.get(venue=self.venue, section=section, row_number=1, seat_number=1)
            self.assertEqual(hold_seat(fan, self.event, seat).status, 'pending')

    def test_seat_label(self):
        seat = Seat.objects.get(venue=self.venue, section='Foldable red', row_number=2, seat_number=3)
        self.assertEqual(seat.label, 'Foldable red, Row 2, Seat 3')


class SimpleVenueStillWorksTests(APITestCase):
    def test_seat_without_layout_has_no_photo_or_section(self):
        venue = Venue.objects.create(name='Plain', location='Nairobi', capacity=1)
        category = SeatCategory.objects.create(venue=venue, name='Regular', price=Decimal('100'))
        seat = Seat.objects.create(venue=venue, row_number=1, seat_number=1, category=category)
        event = Event.objects.create(title='M', venue=venue, event_date=date.today() + timedelta(days=3), event_time=time(15))
        row = self.client.get(f'/api/events/{event.id}/seats/').data['seats'][0]
        self.assertIsNone(row['view_photo'])
        self.assertEqual(row['section'], '')
        self.assertEqual(seat.label, 'Row 1, Seat 1')
