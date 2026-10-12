import io
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from bookings.models import Booking
from events.models import Event
from payments.models import Payment
from tickets.models import Ticket
from users.models import User
from venues.models import Venue, SeatCategory, Seat


class DashboardTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venue = Venue.objects.create(name='Kasarani', location='Nairobi', capacity=4)
        cls.other_venue = Venue.objects.create(name='Nyayo', location='Nairobi', capacity=1)
        vip = SeatCategory.objects.create(venue=cls.venue, name='VIP', price=Decimal('3000'))
        reg = SeatCategory.objects.create(venue=cls.venue, name='Regular', price=Decimal('1000'))
        other_cat = SeatCategory.objects.create(venue=cls.other_venue, name='Regular', price=Decimal('500'))
        cls.seats = [Seat.objects.create(venue=cls.venue, row_number=1, seat_number=n,
                                         category=vip if n <= 2 else reg) for n in (1, 2, 3, 4)]
        cls.other_seat = Seat.objects.create(venue=cls.other_venue, row_number=1, seat_number=1, category=other_cat)

        cls.fan = User.objects.create_user(username='fan', password='x')
        cls.organizer = User.objects.create_user(username='org', password='x', role='organizer')
        cls.rival = User.objects.create_user(username='rival', password='x', role='organizer')
        cls.admin = User.objects.create_user(username='boss', password='x', role='admin')

        cls.event = Event.objects.create(title='Match A', venue=cls.venue, event_time=time(15), organizer=cls.organizer,
                                         event_date=date.today() + timedelta(days=5))
        cls.other_event = Event.objects.create(title='Match B', venue=cls.other_venue, event_time=time(15),
                                               organizer=cls.organizer, event_date=date.today() + timedelta(days=5))

        today = timezone.localdate()
        cls.sell(cls.event, cls.seats[0], today, used=True)                       # VIP 3000 today
        cls.sell(cls.event, cls.seats[2], today - timedelta(days=3))              # Regular 1000
        cls.sell(cls.event, cls.seats[3], today - timedelta(days=60))             # outside 30 days
        cls.sell(cls.other_event, cls.other_seat, today - timedelta(days=1))      # other venue 500
        Booking.objects.create(fan=cls.fan, event=cls.event, seat=cls.seats[1], status='pending',
                               hold_expires_at=timezone.now() + timedelta(minutes=10))
        refund = Booking.objects.create(fan=cls.fan, event=cls.other_event, seat=cls.other_seat, status='expired')
        Payment.objects.create(booking=refund, amount=Decimal('500'), status='refund_due', checkout_request_id='r1')

    @classmethod
    def sell(cls, event, seat, day, used=False):
        at = timezone.make_aware(datetime.combine(day, time(12)))
        booking = Booking.objects.create(fan=cls.fan, event=event, seat=seat, status='confirmed')
        Booking.objects.filter(pk=booking.pk).update(booking_date=at)
        Payment.objects.create(booking=booking, amount=seat.category.price, status='completed',
                               payment_date=at, checkout_request_id=f'c{booking.pk}')
        Ticket.objects.create(booking=booking, qr_token=f't{booking.pk}', is_used=used)

    def get(self, user=None, **params):
        self.client.force_authenticate(user or self.organizer)
        res = self.client.get('/api/reports/dashboard/', params)
        self.assertEqual(res.status_code, 200)
        return res.data

    def test_fans_and_anonymous_cannot_see_reports(self):
        self.assertEqual(self.client.get('/api/reports/dashboard/').status_code, 401)
        self.client.force_authenticate(self.fan)
        self.assertEqual(self.client.get('/api/reports/dashboard/').status_code, 403)

    def test_summary_for_last_30_days(self):
        data = self.get(days='30')
        self.assertEqual(data['summary']['revenue'], '4500.00')    # 3000 + 1000 + 500
        self.assertEqual(data['summary']['tickets_sold'], 3)
        self.assertEqual(data['summary']['average_price'], '1500.00')
        self.assertEqual(data['summary']['refunds_due'], {'count': 1, 'amount': '500.00'})
        self.assertEqual(data['period']['days'], 30)

    def test_all_time_includes_older_sales(self):
        data = self.get(days='all')
        self.assertEqual(data['summary']['revenue'], '5500.00')
        self.assertEqual(data['summary']['tickets_sold'], 4)

    def test_daily_series_fills_every_day(self):
        data = self.get(days='7')
        self.assertEqual(len(data['daily']), 7)
        today = data['daily'][-1]
        self.assertEqual((today['revenue'], today['tickets']), ('3000.00', 1))
        self.assertEqual(sum(d['tickets'] for d in data['daily']), 3)

    def test_revenue_by_category(self):
        data = self.get(days='30', venue=self.venue.id)
        self.assertEqual(data['by_category'], [
            {'category': 'VIP', 'revenue': '3000.00', 'tickets': 1},
            {'category': 'Regular', 'revenue': '1000.00', 'tickets': 1},
        ])

    def test_venue_filter_narrows_everything(self):
        data = self.get(days='30', venue=self.other_venue.id)
        self.assertEqual(data['summary']['revenue'], '500.00')
        self.assertEqual([e['title'] for e in data['events']], ['Match B'])

    def test_event_rows(self):
        row = next(e for e in self.get()['events'] if e['title'] == 'Match A')
        self.assertEqual(
            {k: row[k] for k in ('capacity', 'sold', 'held', 'occupancy', 'checked_in', 'revenue')},
            {'capacity': 4, 'sold': 3, 'held': 1, 'occupancy': 75.0, 'checked_in': 1, 'revenue': '5000.00'},
        )

    def test_heatmap_only_with_a_venue(self):
        self.assertIsNone(self.get()['heatmap'])
        heatmap = self.get(days='all', venue=self.venue.id)['heatmap']
        self.assertEqual(heatmap['events_with_sales'], 1)
        rates = {s['number']: s['rate'] for s in heatmap['seats']}
        self.assertEqual(rates, {1: 1.0, 2: 0, 3: 1.0, 4: 1.0})

    def test_other_organizer_sees_none_of_these_sales(self):
        data = self.get(user=self.rival, days='all')
        self.assertEqual(data['summary']['revenue'], '0.00')
        self.assertEqual(data['summary']['tickets_sold'], 0)
        self.assertEqual(data['events'], [])
        self.assertEqual(data['venues'], [])
        self.assertEqual(data['scope'], 'mine')
        heatmap = self.get(user=self.rival, days='all', venue=self.venue.id)['heatmap']
        self.assertEqual(heatmap['events_with_sales'], 0)

    def test_organizer_sees_only_own_events_and_venues(self):
        Event.objects.create(title='Rival match', venue=self.venue, organizer=self.rival, event_time=time(15),
                             event_date=date.today() + timedelta(days=9))
        data = self.get(days='all')
        self.assertEqual(sorted(e['title'] for e in data['events']), ['Match A', 'Match B'])
        self.assertEqual(sorted(v['name'] for v in data['venues']), ['Kasarani', 'Nyayo'])

    def test_admin_sees_everything_including_unowned_events(self):
        unowned = Event.objects.create(title='Unowned', venue=self.venue, event_time=time(15),
                                       event_date=date.today() + timedelta(days=9))
        seat = Seat.objects.create(venue=self.venue, row_number=2, seat_number=1,
                                   category=self.seats[0].category)
        self.sell(unowned, seat, timezone.localdate())
        data = self.get(user=self.admin, days='all')
        self.assertEqual(data['summary']['revenue'], '8500.00')   # 5500 + unowned 3000
        self.assertIn('Unowned', [e['title'] for e in data['events']])
        self.assertEqual(data['scope'], 'all')
        # ...while the organizer's own figures are unchanged
        self.assertEqual(self.get(days='all')['summary']['revenue'], '5500.00')

    def test_bad_params_fall_back_to_defaults(self):
        data = self.get(days='banana', venue='abc')
        self.assertEqual(data['period']['days'], 30)
        self.assertIsNone(data['venue'])


class SeedDemoSalesTests(APITestCase):
    def test_seed_and_clear(self):
        call_command('seed_venue', rows=6, seats_per_row=8, no_event=True, stdout=io.StringIO())
        call_command('seed_demo_sales', fans=5, stdout=io.StringIO())
        self.assertEqual(Event.objects.filter(description__startswith='DEMO DATA').count(), 4)
        self.assertGreater(Booking.objects.filter(status='confirmed').count(), 10)
        self.assertTrue(Ticket.objects.filter(is_used=True).exists())          # past matches checked in
        self.assertFalse(Ticket.objects.filter(is_used=True, booking__event__status='upcoming').exists())

        call_command('seed_demo_sales', clear=True, stdout=io.StringIO())
        self.assertFalse(Event.objects.filter(description__startswith='DEMO DATA').exists())
        self.assertFalse(User.objects.filter(username__startswith='demo_fan_').exists())
        self.assertEqual(Booking.objects.count(), 0)
