"""
Organizer dashboard figures.

Two kinds of numbers, labelled as such on the dashboard:
  * Sales in the chosen period - revenue (completed M-Pesa payments by payment date),
    tickets sold (confirmed bookings by booking date), per day and per seat category.
  * Event status - per event, all-time: seats sold, occupancy, revenue, checked in.
Both can be narrowed to one venue. The seat heatmap shows, for one venue, how often each
seat was sold across that venue's events in the period.
Pass an organizer to limit every figure to the events they organise (admins pass None = all).
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from bookings.models import Booking
from events.models import Event
from payments.models import Payment
from venues.models import Seat, Venue

PERIOD_CHOICES = {'7': 7, '30': 30, '90': 90, '365': 365, 'all': None}


def resolve_period(days_param):
    """Return (start_date, end_date) for '7' / '30' / '90' / '365' / 'all' (inclusive dates)."""
    today = timezone.localdate()
    days = PERIOD_CHOICES.get(str(days_param), 30)
    if days is not None:
        return today - timedelta(days=days - 1), today
    first_sale = (Booking.objects.filter(status='confirmed').order_by('booking_date')
                  .values_list('booking_date', flat=True).first())
    start = timezone.localtime(first_sale).date() if first_sale else today
    return min(start, today), today


def _money(value):
    return f'{(value or Decimal("0")):.2f}'


def build_dashboard(days_param='30', venue_id=None, organizer=None):
    start, end = resolve_period(days_param)
    venue = Venue.objects.filter(pk=venue_id).first() if venue_id else None

    sold = Booking.objects.filter(status='confirmed', booking_date__date__range=(start, end))
    paid = Payment.objects.filter(status='completed', payment_date__date__range=(start, end))
    refunds = Payment.objects.filter(status='refund_due', created_at__date__range=(start, end))
    if venue:
        sold = sold.filter(event__venue=venue)
        paid = paid.filter(booking__event__venue=venue)
        refunds = refunds.filter(booking__event__venue=venue)
    if organizer:
        sold = sold.filter(event__organizer=organizer)
        paid = paid.filter(booking__event__organizer=organizer)
        refunds = refunds.filter(booking__event__organizer=organizer)

    revenue = paid.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    tickets_sold = sold.count()
    refund_totals = refunds.aggregate(count=Count('id'), amount=Sum('amount'))

    # --- per day, every day in the period (zeros included) ---
    revenue_by_day = dict(paid.annotate(day=TruncDate('payment_date')).values('day')
                          .annotate(total=Sum('amount')).values_list('day', 'total'))
    tickets_by_day = dict(sold.annotate(day=TruncDate('booking_date')).values('day')
                          .annotate(n=Count('id')).values_list('day', 'n'))
    daily = []
    day = start
    while day <= end:
        daily.append({'date': day.isoformat(), 'revenue': _money(revenue_by_day.get(day)),
                      'tickets': tickets_by_day.get(day, 0)})
        day += timedelta(days=1)

    # --- per seat category (grouped by name, so "VIP" at two venues is one row) ---
    cat_revenue = dict(paid.values('booking__seat__category__name')
                       .annotate(total=Sum('amount')).values_list('booking__seat__category__name', 'total'))
    cat_tickets = dict(sold.values('seat__category__name')
                       .annotate(n=Count('id')).values_list('seat__category__name', 'n'))
    by_category = sorted(
        ({'category': name, 'revenue': _money(cat_revenue.get(name)), 'tickets': cat_tickets.get(name, 0)}
         for name in set(cat_revenue) | set(cat_tickets)),
        key=lambda c: Decimal(c['revenue']), reverse=True,
    )

    return {
        'period': {'start': start.isoformat(), 'end': end.isoformat(), 'days': (end - start).days + 1},
        'venue': {'id': venue.id, 'name': venue.name} if venue else None,
        'summary': {
            'revenue': _money(revenue),
            'tickets_sold': tickets_sold,
            'average_price': _money(revenue / tickets_sold) if tickets_sold else None,
            'refunds_due': {'count': refund_totals['count'], 'amount': _money(refund_totals['amount'])},
        },
        'daily': daily,
        'by_category': by_category,
        'events': event_rows(venue, organizer),
        'heatmap': seat_heatmap(venue, start, end, organizer) if venue else None,
    }


def event_rows(venue=None, organizer=None):
    """All non-cancelled events (newest first) with all-time sales and occupancy."""
    events = Event.objects.exclude(status='cancelled').select_related('venue').order_by('-event_date', '-event_time')
    if venue:
        events = events.filter(venue=venue)
    if organizer:
        events = events.filter(organizer=organizer)
    events = list(events.annotate(
        sold=Count('bookings', filter=Q(bookings__status='confirmed'), distinct=True),
        held=Count('bookings', filter=Q(bookings__status='pending'), distinct=True),
        checked_in=Count('bookings', filter=Q(bookings__status='confirmed', bookings__ticket__is_used=True),
                         distinct=True),
    ))
    capacity = dict(Seat.objects.values('venue').annotate(n=Count('id')).values_list('venue', 'n'))
    revenue = dict(Payment.objects.filter(status='completed', booking__event__in=events)
                   .values('booking__event').annotate(total=Sum('amount'))
                   .values_list('booking__event', 'total'))
    rows = []
    for e in events:
        cap = capacity.get(e.venue_id, 0)
        rows.append({
            'id': e.id, 'title': e.title, 'date': e.event_date.isoformat(), 'status': e.status,
            'venue': e.venue.name, 'capacity': cap, 'sold': e.sold, 'held': e.held,
            'occupancy': round(e.sold / cap * 100, 1) if cap else 0,
            'checked_in': e.checked_in, 'revenue': _money(revenue.get(e.id)),
        })
    return rows


def seat_heatmap(venue, start, end, organizer=None):
    """
    For each seat at the venue: how many of the venue's events it was sold for, counting
    sales made in the period. 'rate' = sold / number of the venue's events with any sales
    in the period, so 1.0 means the seat sold for every one of those events.
    """
    sold = Booking.objects.filter(status='confirmed', event__venue=venue,
                                  booking_date__date__range=(start, end))
    if organizer:
        sold = sold.filter(event__organizer=organizer)
    events_with_sales = sold.values('event').distinct().count()
    sold_per_seat = defaultdict(int, sold.values('seat').annotate(n=Count('id')).values_list('seat', 'n'))
    seats = Seat.objects.filter(venue=venue).select_related('category').order_by('row_number', 'seat_number')
    return {
        'venue': {'id': venue.id, 'name': venue.name},
        'events_with_sales': events_with_sales,
        'seats': [{
            'id': s.id, 'row': s.row_number, 'number': s.seat_number, 'category': s.category.name,
            'sold': sold_per_seat[s.id],
            'rate': round(sold_per_seat[s.id] / events_with_sales, 3) if events_with_sales else 0,
        } for s in seats],
    }
