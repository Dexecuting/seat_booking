from datetime import date, time, timedelta
from decimal import Decimal

from rest_framework.test import APITestCase

from bookings.services import confirm_booking, hold_seat
from events.models import Event
from tickets.models import Ticket
from users.models import User
from venues.models import Venue, SeatCategory, Seat

from .models import GateEntry


class GateScanTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venue = Venue.objects.create(name='Kasarani', location='Nairobi', capacity=2)
        cls.category = SeatCategory.objects.create(venue=cls.venue, name='VIP', price=Decimal('3000'))
        cls.seat = Seat.objects.create(venue=cls.venue, row_number=4, seat_number=12, category=cls.category)
        cls.fan = User.objects.create_user(username='fan', password='x', first_name='Achieng', last_name='Otieno')
        cls.staff = User.objects.create_user(username='gate1', password='x', role='gate_staff')
        cls.organizer = User.objects.create_user(username='org', password='x', role='organizer')

    def setUp(self):
        self.event = self.make_event(date.today())
        self.ticket = self.make_ticket(self.event)
        self.client.force_authenticate(self.staff)

    def make_event(self, event_date, **kwargs):
        return Event.objects.create(title='Gor Mahia vs AFC Leopards', venue=self.venue,
                                    event_date=event_date, event_time=time(15), **kwargs)

    def make_ticket(self, event):
        booking = confirm_booking(hold_seat(self.fan, event, self.seat))
        return Ticket.objects.create(booking=booking, qr_token=Ticket.generate_qr_token())

    def scan(self, token=None, **extra):
        return self.client.post('/api/gates/scan/', {'token': token or self.ticket.qr_token, **extra})

    def test_valid_ticket_is_admitted_and_marked_used(self):
        res = self.scan()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['allowed'])
        self.assertEqual(res.data['ticket']['holder'], 'Achieng Otieno')
        self.assertEqual((res.data['ticket']['row'], res.data['ticket']['seat_number']), (4, 12))
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.is_used)
        self.assertIsNotNone(self.ticket.used_at)

    def test_second_scan_is_denied(self):
        self.scan()
        res = self.scan()
        self.assertFalse(res.data['allowed'])
        self.assertIn('already used', res.data['reason'])

    def test_unknown_token_is_denied_and_logged(self):
        res = self.scan(token='forged-token')
        self.assertFalse(res.data['allowed'])
        self.assertIsNone(res.data['ticket'])
        entry = GateEntry.objects.get()
        self.assertEqual((entry.scanned_token, entry.ticket, entry.entry_allowed), ('forged-token', None, False))

    def test_every_scan_is_logged_with_staff_member(self):
        self.scan()
        self.scan()
        self.assertEqual(list(GateEntry.objects.order_by('id').values_list('entry_allowed', 'scanned_by')),
                         [(True, self.staff.id), (False, self.staff.id)])

    def test_ticket_for_another_day_is_denied(self):
        ticket = self.make_ticket(self.make_event(date.today() + timedelta(days=7)))
        res = self.scan(token=ticket.qr_token)
        self.assertFalse(res.data['allowed'])
        self.assertIn('not today', res.data['reason'])
        ticket.refresh_from_db()
        self.assertFalse(ticket.is_used)

    def test_ticket_for_different_event_at_this_gate_is_denied(self):
        other_event = self.make_event(date.today())
        res = self.scan(event=other_event.id)
        self.assertFalse(res.data['allowed'])
        self.assertIn('different event', res.data['reason'])

    def test_ticket_for_this_gates_event_is_admitted(self):
        self.assertTrue(self.scan(event=self.event.id).data['allowed'])

    def test_cancelled_event_is_denied(self):
        self.event.status = 'cancelled'
        self.event.save()
        self.assertIn('cancelled', self.scan().data['reason'])

    def test_unpaid_booking_is_denied(self):
        booking = self.ticket.booking
        booking.status = 'cancelled'
        booking.save()
        self.assertIn('not paid', self.scan().data['reason'])

    def test_fans_cannot_scan(self):
        self.client.force_authenticate(self.fan)
        self.assertEqual(self.scan().status_code, 403)

    def test_organizer_can_scan_and_view_log(self):
        self.client.force_authenticate(self.organizer)
        self.assertTrue(self.scan().data['allowed'])
        res = self.client.get(f'/api/gates/entries/?ticket__booking__event={self.event.id}')
        self.assertEqual(res.data['count'], 1)
        self.assertEqual(res.data['results'][0]['scanned_by'], 'org')

    def test_gate_staff_cannot_view_log(self):
        self.assertEqual(self.client.get('/api/gates/entries/').status_code, 403)
