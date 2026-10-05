"""
Thin client for Safaricom's Daraja API (M-Pesa Express / STK Push).
Docs: https://developer.safaricom.co.ke/APIs/MpesaExpressSimulate
"""
import base64
import logging
from decimal import ROUND_CEILING, Decimal

import requests
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30
TOKEN_CACHE_KEY = 'daraja_access_token'


class DarajaError(Exception):
    """Daraja could not be reached or rejected the request."""


def _post(path, payload):
    headers = {'Authorization': f'Bearer {get_access_token()}'}
    try:
        res = requests.post(f'{settings.DARAJA_BASE_URL}{path}', json=payload,
                            headers=headers, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.exception('Daraja request to %s failed', path)
        raise DarajaError('Could not reach M-Pesa. Please try again.') from exc
    try:
        data = res.json()
    except ValueError:
        data = {}
    if res.status_code != 200:
        logger.warning('Daraja %s returned %s: %s', path, res.status_code, res.text)
        raise DarajaError(data.get('errorMessage') or f'M-Pesa returned HTTP {res.status_code}.')
    return data


def get_access_token():
    """OAuth token, cached until shortly before it expires (Daraja tokens last 1 hour)."""
    token = cache.get(TOKEN_CACHE_KEY)
    if token:
        return token
    if not (settings.DARAJA_CONSUMER_KEY and settings.DARAJA_CONSUMER_SECRET):
        raise DarajaError('M-Pesa is not configured (DARAJA_CONSUMER_KEY/SECRET missing).')
    try:
        res = requests.get(
            f'{settings.DARAJA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials',
            auth=(settings.DARAJA_CONSUMER_KEY, settings.DARAJA_CONSUMER_SECRET),
            timeout=TIMEOUT_SECONDS,
        )
        res.raise_for_status()
        data = res.json()
    except (requests.RequestException, ValueError) as exc:
        logger.exception('Daraja authentication failed')
        raise DarajaError('Could not authenticate with M-Pesa.') from exc
    cache.set(TOKEN_CACHE_KEY, data['access_token'], int(data.get('expires_in', 3599)) - 60)
    return data['access_token']


def _password_and_timestamp():
    timestamp = timezone.localtime().strftime('%Y%m%d%H%M%S')
    raw = f'{settings.DARAJA_BUSINESS_SHORTCODE}{settings.DARAJA_PASSKEY}{timestamp}'
    return base64.b64encode(raw.encode()).decode(), timestamp


def callback_url():
    if not (settings.DARAJA_CALLBACK_BASE_URL and settings.DARAJA_CALLBACK_TOKEN):
        raise DarajaError('M-Pesa is not configured (DARAJA_CALLBACK_BASE_URL/TOKEN missing).')
    path = reverse('mpesa-callback', kwargs={'token': settings.DARAJA_CALLBACK_TOKEN})
    return settings.DARAJA_CALLBACK_BASE_URL.rstrip('/') + path


def stk_push(phone, amount, account_reference, description):
    """
    Send the PIN prompt to the customer's phone. Returns Daraja's response, which includes
    CheckoutRequestID (used to match the callback). The result arrives later via the callback.
    """
    password, timestamp = _password_and_timestamp()
    data = _post('/mpesa/stkpush/v1/processrequest', {
        'BusinessShortCode': settings.DARAJA_BUSINESS_SHORTCODE,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': int(Decimal(amount).to_integral_value(ROUND_CEILING)),  # M-Pesa takes whole shillings
        'PartyA': phone,
        'PartyB': settings.DARAJA_BUSINESS_SHORTCODE,
        'PhoneNumber': phone,
        'CallBackURL': callback_url(),
        'AccountReference': account_reference[:12],
        'TransactionDesc': description[:13],
    })
    if str(data.get('ResponseCode')) != '0':
        raise DarajaError(data.get('ResponseDescription') or 'M-Pesa rejected the payment request.')
    return data


def stk_query(checkout_request_id):
    """
    Ask Daraja for the result of an STK Push. Useful when the callback can't reach the server
    (e.g. local development without ngrok). Raises DarajaError while still being processed.
    """
    password, timestamp = _password_and_timestamp()
    return _post('/mpesa/stkpushquery/v1/query', {
        'BusinessShortCode': settings.DARAJA_BUSINESS_SHORTCODE,
        'Password': password,
        'Timestamp': timestamp,
        'CheckoutRequestID': checkout_request_id,
    })
