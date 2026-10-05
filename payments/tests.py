import base64
from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from bookings.models import Booking
from bookings.services import hold_seat
from events.models import Event
from tickets.models import Ticket
from users.models import User
from venues.models import Venue, SeatCategory, Seat

from . import daraja
from .models import Payment

DARAJA_SETTINGS = dict(
    DARAJA_CONSUMER_KEY='key', DARAJA_CONSUMER_SECRET='secret',
    DARAJA_BUSINESS_SHORTCODE='174379', DARAJA_PASSKEY='passkey',
    DARAJA_CALLBACK_BASE_URL='https://example.ngrok-free.app', DARAJA_CALLBACK_TOKEN='s3cret',
)
STK_ACCEPTED = {'MerchantRequestID': 'm-1', 'CheckoutRequestID': 'ws_CO_1',
                'ResponseCode': '0', 'CustomerMessage': 'Success. Request accepted for processing'}


def callback_payload(result_code=0, checkout_id='ws_CO_1', receipt='SGH7XYZ123'):
    cb = {'MerchantRequestID': 'm-1', 'CheckoutRequestID': checkout_id,
          'ResultCode': result_code, 'ResultDesc': 'ok' if result_code == 0 else 'Request cancelled by user'}
    if result_code == 0:
        cb['CallbackMetadata'] = {'Item': [
            {'Name': 'Amount', 'Value': 1000},
            {'Name': 'MpesaReceiptNumber', 'Value': receipt},
            {'Name': 'PhoneNumber', 'Value': 254712345678},
        ]}
    return {'Body': {'stkCallback': cb}}


@override_settings(**DARAJA_SETTINGS)
@mock.patch('payments.daraja.stk_push', return_value=STK_ACCEPTED)
class PaymentApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        venue = Venue.objects.create(name='Kasarani', location='Nairobi', capacity=1)
        category = SeatCategory.objects.create(venue=venue, name='Regular', price=Decimal('1000'))
        cls.seat = Seat.objects.create(venue=venue, row_number=1, seat_number=1, category=category)
        cls.event = Event.objects.create(title='Match', venue=venue,
                                         event_date=date.today() + timedelta(days=7), event_time=time(15))
        cls.fan = User.objects.create_user(username='fan', password='x', phone='254712345678')
        cls.other_fan = User.objects.create_user(username='other', password='x', phone='254700000000')

    def setUp(self):
        self.booking = hold_seat(self.fan, self.event, self.seat)
        self.client.force_authenticate(self.fan)

    def pay(self, **data):
        return self.client.post('/api/payments/', {'booking': self.booking.id, **data})

    def callback(self, payload, token='s3cret'):
        self.client.force_authenticate(None)
        return self.client.post(f'/api/payments/mpesa/callback/{token}/', payload, format='json')

    # starting a payment

    def test_start_payment_sends_stk_push(self, stk_push):
        res = self.pay()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['status'], 'pending')
        stk_push.assert_called_once_with(phone='254712345678', amount=Decimal('1000.00'),
                                         account_reference=f'BK{self.booking.id}',
                                         description='Seat booking')
        self.assertEqual(Payment.objects.get().checkout_request_id, 'ws_CO_1')

    def test_can_pay_with_a_different_phone(self, stk_push):
        self.pay(phone='0722 000 111')
        self.assertEqual(stk_push.call_args.kwargs['phone'], '254722000111')

    def test_cannot_pay_for_another_fans_booking(self, stk_push):
        self.client.force_authenticate(self.other_fan)
        self.assertEqual(self.pay().status_code, 400)
        stk_push.assert_not_called()

    def test_cannot_pay_for_expired_hold(self, stk_push):
        Booking.objects.filter(pk=self.booking.pk).update(hold_expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.pay().status_code, 400)
        stk_push.assert_not_called()

    def test_cannot_start_second_payment_while_one_pending(self, stk_push):
        self.pay()
        res = self.pay()
        self.assertEqual(res.status_code, 400)
        self.assertEqual(stk_push.call_count, 1)

    def test_daraja_error_is_reported(self, stk_push):
        stk_push.side_effect = daraja.DarajaError('Could not reach M-Pesa. Please try again.')
        res = self.pay()
        self.assertEqual(res.status_code, 400)
        self.assertIn('M-Pesa', res.data['detail'])
        self.assertFalse(Payment.objects.exists())

    def test_cannot_release_hold_while_payment_pending(self, stk_push):
        self.pay()
        self.assertEqual(self.client.delete(f'/api/bookings/{self.booking.id}/').status_code, 400)

    # callback

    def test_successful_callback_confirms_booking_and_issues_ticket(self, stk_push):
        self.pay()
        res = self.callback(callback_payload())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['ResultCode'], 0)

        payment = Payment.objects.get()
        self.booking.refresh_from_db()
        self.assertEqual((payment.status, payment.mpesa_reference), ('completed', 'SGH7XYZ123'))
        self.assertEqual(self.booking.status, 'confirmed')
        self.assertTrue(Ticket.objects.filter(booking=self.booking).exists())

    def test_cancelled_callback_marks_failed_and_allows_retry(self, stk_push):
        self.pay()
        self.callback(callback_payload(result_code=1032))
        self.assertEqual(Payment.objects.get().status, 'failed')
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'pending')

        stk_push.return_value = {**STK_ACCEPTED, 'CheckoutRequestID': 'ws_CO_2'}
        self.client.force_authenticate(self.fan)
        self.assertEqual(self.pay().status_code, 201)

    def test_duplicate_callback_is_ignored(self, stk_push):
        self.pay()
        self.callback(callback_payload())
        self.callback(callback_payload(result_code=1032))  # late/duplicate - must not undo success
        self.assertEqual(Payment.objects.get().status, 'completed')
        self.assertEqual(Ticket.objects.count(), 1)

    def test_payment_after_hold_lapsed_is_flagged_for_refund(self, stk_push):
        self.pay()
        Booking.objects.filter(pk=self.booking.pk).update(hold_expires_at=timezone.now() - timedelta(seconds=1))
        self.callback(callback_payload())
        self.booking.refresh_from_db()
        self.assertEqual(Payment.objects.get().status, 'refund_due')
        self.assertEqual(self.booking.status, 'expired')
        self.assertFalse(Ticket.objects.exists())

    def test_callback_with_wrong_token_is_rejected(self, stk_push):
        self.pay()
        self.assertEqual(self.callback(callback_payload(), token='guess').status_code, 404)
        self.assertEqual(Payment.objects.get().status, 'pending')

    def test_callback_for_unknown_checkout_is_acknowledged(self, stk_push):
        res = self.callback(callback_payload(checkout_id='unknown'))
        self.assertEqual(res.status_code, 200)

    def test_malformed_callback_is_acknowledged(self, stk_push):
        self.assertEqual(self.callback({'nonsense': True}).status_code, 200)

    # polling

    def test_refresh_applies_result_from_stk_query(self, stk_push):
        payment_id = self.pay().data['id']
        with mock.patch('payments.daraja.stk_query',
                        return_value={'ResultCode': '0', 'ResultDesc': 'processed successfully'}):
            res = self.client.post(f'/api/payments/{payment_id}/refresh/')
        self.assertEqual(res.data['status'], 'completed')
        self.assertEqual(res.data['booking_status'], 'confirmed')

    def test_refresh_while_processing_stays_pending(self, stk_push):
        payment_id = self.pay().data['id']
        with mock.patch('payments.daraja.stk_query',
                        side_effect=daraja.DarajaError('The transaction is being processed')):
            res = self.client.post(f'/api/payments/{payment_id}/refresh/')
        self.assertEqual(res.data['status'], 'pending')

    def test_payments_list_only_shows_mine(self, stk_push):
        self.pay()
        self.client.force_authenticate(self.other_fan)
        self.assertEqual(self.client.get('/api/payments/').data['count'], 0)


@override_settings(**DARAJA_SETTINGS)
class DarajaClientTests(APITestCase):
    def setUp(self):
        cache.clear()

    @mock.patch('payments.daraja.requests')
    def test_stk_push_request(self, requests):
        requests.get.return_value.json.return_value = {'access_token': 'tok', 'expires_in': '3599'}
        requests.post.return_value.status_code = 200
        requests.post.return_value.json.return_value = STK_ACCEPTED

        self.assertEqual(daraja.stk_push('254712345678', Decimal('999.50'), 'BK123456789012345', 'Seat booking'),
                         STK_ACCEPTED)

        url = requests.post.call_args.args[0]
        body = requests.post.call_args.kwargs['json']
        self.assertEqual(url, 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest')
        self.assertEqual(requests.post.call_args.kwargs['headers'], {'Authorization': 'Bearer tok'})
        self.assertEqual(body['Amount'], 1000)  # rounded up to whole shillings
        self.assertEqual(body['AccountReference'], 'BK1234567890')  # max 12 chars
        self.assertEqual(body['CallBackURL'],
                         'https://example.ngrok-free.app/api/payments/mpesa/callback/s3cret/')
        self.assertEqual(base64.b64decode(body['Password']).decode(),
                         f"174379passkey{body['Timestamp']}")

    @mock.patch('payments.daraja.requests')
    def test_access_token_is_cached(self, requests):
        requests.get.return_value.json.return_value = {'access_token': 'tok', 'expires_in': '3599'}
        daraja.get_access_token()
        daraja.get_access_token()
        self.assertEqual(requests.get.call_count, 1)

    @override_settings(DARAJA_CONSUMER_KEY='')
    def test_missing_credentials_raise_clear_error(self):
        with self.assertRaisesMessage(daraja.DarajaError, 'not configured'):
            daraja.get_access_token()
