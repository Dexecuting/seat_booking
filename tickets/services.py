import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction

from .models import Ticket
from .qr_generator import qr_png

logger = logging.getLogger(__name__)


def issue_ticket(booking):
    """
    Create the ticket for a confirmed booking (once) and email it to the fan after the
    surrounding transaction commits. Returns the Ticket.
    """
    ticket, created = Ticket.objects.get_or_create(
        booking=booking, defaults={'qr_token': Ticket.generate_qr_token()})
    if created:
        transaction.on_commit(lambda: send_ticket_email(ticket))
    return ticket


def send_ticket_email(ticket):
    """Email the ticket with its QR code attached. Failures are logged, never raised:
    the fan can still open the ticket in the app."""
    booking = ticket.booking
    fan, event, seat = booking.fan, booking.event, booking.seat
    if not fan.email:
        logger.warning('Ticket %s not emailed: fan %s has no email address', ticket.id, fan.id)
        return False

    body = (
        f"Hi {fan.first_name or fan.username},\n\n"
        f"Your seat is confirmed. Show the attached QR code at the gate.\n\n"
        f"Event:  {event.title}\n"
        f"Venue:  {event.venue.name}, {event.venue.location}\n"
        f"Date:   {event.event_date:%A %d %B %Y} at {event.event_time:%H:%M}\n"
        f"Seat:   Row {seat.row_number}, Seat {seat.seat_number} ({seat.category.name})\n"
        f"Ticket: #{ticket.id}\n\n"
        f"The QR code can only be used once. Do not share it.\n"
    )
    message = EmailMessage(
        subject=f'Your ticket: {event.title}',
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[fan.email],
    )
    message.attach(f'ticket-{ticket.id}.png', qr_png(ticket.qr_token), 'image/png')
    try:
        message.send()
    except Exception:
        logger.exception('Failed to email ticket %s to %s', ticket.id, fan.email)
        return False
    return True
