"""
Server-side QR validation at the gate. The QR holds only a random token, so a ticket
can't be forged or edited; it is checked against the database and marked used atomically,
so the same QR can't get two people in even if scanned at two gates simultaneously.
"""
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from tickets.models import Ticket

from .models import GateEntry


@dataclass
class ScanResult:
    allowed: bool
    reason: str
    ticket: Ticket | None = None


def _check(ticket, event_id):
    """Return the reason to deny entry, or None if the ticket is valid right now."""
    booking = ticket.booking
    event = booking.event
    if event_id is not None and event.id != event_id:
        return f'Ticket is for a different event: {event.title}.'
    if booking.status != 'confirmed':
        return 'Ticket is not paid for.'
    if event.status == 'cancelled':
        return 'This event has been cancelled.'
    if event.event_date != timezone.localdate():
        return f'Ticket is for {event.event_date:%d %b %Y}, not today.'
    if ticket.is_used:
        return f'Ticket already used at {timezone.localtime(ticket.used_at):%H:%M}.'
    return None


def validate_ticket(token, scanned_by=None, event_id=None):
    """
    Check a scanned QR token and, if valid, mark the ticket used. Every scan is logged.
    Pass event_id to also reject tickets for other events (the event this gate is serving).
    """
    token = (token or '').strip()
    with transaction.atomic():
        ticket = (Ticket.objects.select_for_update()
                  .select_related('booking__event__venue', 'booking__seat__category', 'booking__fan')
                  .filter(qr_token=token).first()) if token else None

        if ticket is None:
            result = ScanResult(False, 'Invalid ticket - not recognised.')
        else:
            reason = _check(ticket, event_id)
            if reason:
                result = ScanResult(False, reason, ticket)
            else:
                ticket.is_used = True
                ticket.used_at = timezone.now()
                ticket.save(update_fields=['is_used', 'used_at'])
                result = ScanResult(True, 'Entry allowed.', ticket)

        GateEntry.objects.create(
            ticket=ticket, scanned_token=token[:255], scanned_by=scanned_by,
            entry_allowed=result.allowed, notes=result.reason[:255],
        )
    return result
