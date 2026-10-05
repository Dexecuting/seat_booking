from datetime import date, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from events.models import Event
from venues.models import Venue, SeatCategory, Seat


# Rows are assigned front-to-back: the first rows are VIP, then Regular, then Student.
CATEGORIES = [
    # (name, price in KES, share of rows, description)
    ('VIP', Decimal('3000.00'), 0.2, 'Covered seating closest to the pitch, halfway line view'),
    ('Regular', Decimal('1000.00'), 0.5, 'Mid-tier seating with a full view of the pitch'),
    ('Student', Decimal('300.00'), 0.3, 'Upper rows, elevated view of the whole pitch'),
]


class Command(BaseCommand):
    help = 'Seed a venue with seat categories, seats and a sample event for development.'

    def add_arguments(self, parser):
        parser.add_argument('--name', default='Kasarani Stadium')
        parser.add_argument('--location', default='Nairobi, Kenya')
        parser.add_argument('--rows', type=int, default=20)
        parser.add_argument('--seats-per-row', type=int, default=30)
        parser.add_argument('--no-event', action='store_true', help='Do not create a sample event.')
        parser.add_argument('--reset', action='store_true',
                            help='Delete the venue (and its seats, events and bookings) first if it exists.')

    @transaction.atomic
    def handle(self, *args, **opts):
        name, rows, per_row = opts['name'], opts['rows'], opts['seats_per_row']

        if opts['reset']:
            deleted, _ = Venue.objects.filter(name=name).delete()
            if deleted:
                self.stdout.write(self.style.WARNING(f'Deleted existing "{name}" and related data.'))

        if Venue.objects.filter(name=name).exists():
            self.stdout.write(self.style.WARNING(
                f'Venue "{name}" already exists. Use --reset to recreate it.'))
            return

        venue = Venue.objects.create(
            name=name,
            location=opts['location'],
            capacity=rows * per_row,
            description=f'Seeded venue with {rows} rows of {per_row} seats.',
        )

        # Work out which category each row belongs to.
        row_categories = []
        for cat_name, price, share, description in CATEGORIES:
            category = SeatCategory.objects.create(
                venue=venue, name=cat_name, price=price, description=description)
            row_categories += [category] * max(1, round(rows * share))
        row_categories = (row_categories + [row_categories[-1]] * rows)[:rows]

        Seat.objects.bulk_create([
            Seat(venue=venue, row_number=row, seat_number=seat, category=row_categories[row - 1])
            for row in range(1, rows + 1)
            for seat in range(1, per_row + 1)
        ])

        self.stdout.write(self.style.SUCCESS(
            f'Created "{venue.name}" with {len(CATEGORIES)} categories and {rows * per_row} seats.'))

        if not opts['no_event']:
            event = Event.objects.create(
                title='Gor Mahia vs AFC Leopards',
                description='Mashemeji Derby - Kenyan Premier League',
                venue=venue,
                event_date=date.today() + timedelta(days=14),
                event_time=time(15, 0),
            )
            self.stdout.write(self.style.SUCCESS(f'Created sample event "{event}".'))
