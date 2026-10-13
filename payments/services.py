"""
Payment flow:
  1. start_payment()  - fan has a pending booking; send STK Push, record a pending Payment.
  2. Fan enters their M-Pesa PIN on their phone.
  3. Safaricom posts the result to the callback -> process_stk_callback() -> apply_result().
     (Or, without a public callback URL, refresh_from_daraja() polls for it.)
  4. On success the booking is confirmed and a ticket issued. If the hold lapsed before
     payment arrived, the payment is flagged 'refund_due' and the seat stays free.
"""
import logging

from django.conf import settings

from django.db import transaction
from django.utils import timezone

from bookings.services import HoldExpired, confirm_booking
from tickets.services import issue_ticket

from . import daraja
from .models import Payment

logger = logging.getLogger(__name__)


# Daraja STK query result codes meaning "no final answer yet" - not a failure.
STILL_PROCESSING_CODES = {'4999', '500.001.1001'}


class PaymentError(Exception):
    """A payment could not be started; the message is safe to show the fan."""


def start_payment(booking, phone):
    if booking.status != 'pending' or booking.is_hold_expired():
        raise PaymentError('This seat is no longer held. Please select your seat again.')
    if booking.payments.filter(status='pending').exists():
        raise PaymentError('A payment request was already sent to your phone. '
                           'Complete it or wait for it to time out.')

    amount = booking.seat.category.price
    charge = settings.DARAJA_TEST_AMOUNT or amount  # small fixed charge while testing (see settings)
    try:
        res = daraja.stk_push(
            phone=phone,
            amount=charge,
            account_reference=f'BK{booking.id}',
            description='Seat booking',
        )
    except daraja.DarajaError as exc:
        raise PaymentError(str(exc)) from exc

    logger.info('STK push sent: booking %s, ticket price KES %s, charged KES %s, CheckoutRequestID %s',
                booking.id, amount, charge, res.get('CheckoutRequestID'))
    return Payment.objects.create(
        booking=booking,
        amount=amount,
        phone=phone,
        checkout_request_id=res['CheckoutRequestID'],
        merchant_request_id=res.get('MerchantRequestID', ''),
    )


def apply_result(checkout_request_id, result_code, result_desc, receipt=''):
    """
    Record the outcome of an STK Push. Safe to call more than once for the same payment
    (Safaricom may retry callbacks): once a payment is completed (or refund_due) nothing changes.
    A success always wins over an earlier 'failed', because the money really arrived - e.g. a
    status query guessed wrong and the real callback came in afterwards.
    Returns the Payment, or None if the checkout ID is unknown.
    """
    with transaction.atomic():
        payment = (Payment.objects.select_for_update()
                   .select_related('booking').filter(checkout_request_id=checkout_request_id).first())
        if payment is None:
            logger.warning('M-Pesa result for unknown CheckoutRequestID %s', checkout_request_id)
            return None
        succeeded = str(result_code) == '0'
        if payment.status in ('completed', 'refund_due'):
            return payment
        if payment.status == 'failed':
            if not succeeded:
                return payment
            logger.warning('Payment %s was marked failed but M-Pesa now reports success (%s) - applying it',
                           payment.id, receipt or 'no receipt')

        payment.result_code = str(result_code)
        payment.result_desc = (result_desc or '')[:255]
        if not succeeded:
            payment.status = 'failed'
            payment.save()
            return payment

        payment.mpesa_reference = receipt or ''
        payment.payment_date = timezone.now()
        try:
            payment.booking = confirm_booking(payment.booking)
        except HoldExpired:
            logger.error('Payment %s (%s) received after hold on booking %s lapsed - refund due',
                         payment.id, receipt, payment.booking_id)
            payment.booking.refresh_from_db()
            payment.status = 'refund_due'
        else:
            payment.status = 'completed'
            issue_ticket(payment.booking)
        payment.save()
        return payment


def process_stk_callback(payload):
    """Handle the JSON Safaricom posts to the callback URL."""
    try:
        cb = payload['Body']['stkCallback']
        checkout_id = cb['CheckoutRequestID']
        result_code = cb['ResultCode']
    except (KeyError, TypeError):
        logger.warning('Malformed M-Pesa callback: %s', payload)
        return None
    items = {item.get('Name'): item.get('Value')
             for item in cb.get('CallbackMetadata', {}).get('Item', [])}
    return apply_result(checkout_id, result_code, cb.get('ResultDesc', ''),
                        receipt=str(items.get('MpesaReceiptNumber', '')))


def refresh_from_daraja(payment):
    """Poll Daraja for a pending payment's result. Leaves it pending if still processing."""
    if payment.status != 'pending':
        return payment
    try:
        res = daraja.stk_query(payment.checkout_request_id)
    except daraja.DarajaError:
        return payment  # still being processed, or Daraja unavailable - try again later
    code = str(res.get('ResultCode', '')).strip()
    logger.info('STK query for payment %s: %s %s', payment.id, code, res.get('ResultDesc', ''))
    if not code or code in STILL_PROCESSING_CODES:
        return payment  # no final answer yet (e.g. 4999 "still under processing")
    return apply_result(payment.checkout_request_id, code, res.get('ResultDesc', ''))
