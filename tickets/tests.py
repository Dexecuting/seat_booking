from datetime import date, time, timedelta
from decimal import Decimal

from django.core import mail
from rest_framework.test import APITestCase

from bookings.services import confirm_booking, hold_seat
from events.models import Event
from users.models import User
from venues.models import Venue, SeatCategory, Seat

from .models import Ticket
from .services import issue_ticket


class TicketTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        venue = Venue.objects.create(name='Kasarani', location='Nairobi', capacity=2)
        category = SeatCategory.objects.create(venue=venue, name='VIP', price=Decimal('3000'))
        cls.seat = Seat.objects.create(venue=venue, row_number=4, seat_number=12, category=category)
        cls.event = Event.objects.create(title='Gor Mahia vs AFC Leopards', venue=venue,
                                         event_date=date.today() + timedelta(days=7), event_time=time(15))
        cls.fan = User.objects.create_user(username='fan', password='x', email='fan@example.com',
                                           first_name='Achieng')
        cls.other_fan = User.objects.create_user(username='other', password='x')

    def setUp(self):
        self.booking = confirm_booking(hold_seat(self.fan, self.event, self.seat))

    def issue(self):
        with self.captureOnCommitCallbacks(execute=True):
            return issue_ticket(self.booking)

    def test_issue_ticket_emails_qr_code(self):
        ticket = self.issue()
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['fan@example.com'])
        self.assertIn('Gor Mahia vs AFC Leopards', email.subject)
        self.assertIn('Row 4, Seat 12 (VIP)', email.body)
        name, content, mimetype = email.attachments[0]
        self.assertEqual((name, mimetype), (f'ticket-{ticket.id}.png', 'image/png'))
        self.assertTrue(content.startswith(b'\x89PNG'))

    def test_issue_ticket_is_idempotent(self):
        first = self.issue()
        second = self.issue()
        self.assertEqual(first, second)
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_fan_without_email_still_gets_ticket(self):
        self.fan.email = ''
        self.fan.save()
        self.issue()
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_list_my_tickets(self):
        self.issue()
        self.client.force_authenticate(self.fan)
        res = self.client.get('/api/tickets/')
        self.assertEqual(res.data['count'], 1)
        ticket = res.data['results'][0]
        self.assertEqual((ticket['row'], ticket['seat_number'], ticket['venue']), (4, 12, 'Kasarani'))
        self.assertNotIn('qr_code', ticket)

    def test_ticket_detail_includes_qr_image(self):
        ticket = self.issue()
        self.client.force_authenticate(self.fan)
        res = self.client.get(f'/api/tickets/{ticket.id}/')
        self.assertTrue(res.data['qr_code'].startswith('data:image/png;base64,'))
        self.assertNotIn('qr_token', res.data)

    def test_cannot_see_another_fans_ticket(self):
        ticket = self.issue()
        self.client.force_authenticate(self.other_fan)
        self.assertEqual(self.client.get(f'/api/tickets/{ticket.id}/').status_code, 404)

    def test_resend_ticket(self):
        ticket = self.issue()
        self.client.force_authenticate(self.fan)
        res = self.client.post(f'/api/tickets/{ticket.id}/resend/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)
