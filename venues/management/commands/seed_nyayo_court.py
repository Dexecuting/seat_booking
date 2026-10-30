"""
Create the Nyayo Stadium handball court: its real 912 seats, prices and the photo from each seat.

    python manage.py seed_nyayo_court                     # create the venue and seats
    python manage.py seed_nyayo_court --photos "<folder>" # also build the web photos from the originals

The layout comes from the on-site photo shoot. Each row lists its photos as positions in the
originals folder sorted by filename (position 1 is an overview of the stands, so seats start at 2),
walking across the row from the left of the map. On the map the first side is drawn above the court
and the second side below it, so both walks run from map-left to map-right.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, ImageOps

from events.models import Event
from venues.models import Seat, SeatCategory, Venue

VENUE_NAME = 'Nyayo Stadium Handball Court'
PHOTO_DIR = 'venues/nyayo-handball'
PHOTO_MAX_SIZE = (720, 1600)
PHOTO_QUALITY = 75

FRONT, FOLDABLE, STANDARD = 'Front row', 'Foldable', 'Standard'
CATEGORIES = {
    FRONT: (Decimal('350.00'), 'Front row, closest to the court'),
    FOLDABLE: (Decimal('250.00'), 'Foldable seats in the three central blocks of the second side'),
    STANDARD: (Decimal('100.00'), 'Standard seating, rows 2 to 5'),
}


def run(first, last, skip=()):
    return [p for p in range(first, last + 1) if p not in skip]


# (stand, section, section_order, always-this-category or None, {row: photo positions})
LAYOUT = [
    ('first', 'First side', 1, None, {
        1: run(2, 89), 2: run(90, 179), 3: run(180, 272), 4: run(273, 367), 5: run(368, 467),
    }),
    ('second', 'Green section', 1, None, {
        # Position 643 is left out: row 2 has 30 photos for 29 seats, and it is the closest near-duplicate.
        1: run(468, 496), 2: run(637, 666, skip={643}), 3: run(703, 731), 4: run(770, 798), 5: run(840, 868),
    }),
    ('second', 'Foldable green', 2, FOLDABLE, {
        1: run(497, 502), 2: run(518, 523), 3: run(540, 545), 4: run(562, 567), 5: run(584, 589),
    }),
    ('second', 'Foldable red', 3, FOLDABLE, {
        1: run(503, 512), 2: run(524, 533), 3: run(546, 555), 4: run(568, 577), 5: run(590, 597),
    }),
    ('second', 'Foldable black', 4, FOLDABLE, {
        # No photo was taken from the last seat of row 1, so it shares its neighbour's.
        1: run(513, 517) + [517], 2: run(534, 539), 3: run(556, 561), 4: run(578, 583), 5: run(598, 603),
    }),
    ('second', 'Black section', 5, None, {
        1: run(604, 636), 2: run(667, 702), 3: run(732, 769), 4: run(799, 839), 5: run(869, 913),
    }),
]


def seat_plan():
    """Yield (stand, section, order, category, row, seat number, photo position, photo file name)."""
    for stand, section, order, fixed, rows in LAYOUT:
        slug = section.lower().replace(' ', '-')
        for row, positions in rows.items():
            category = fixed or (FRONT if row == 1 else STANDARD)
            for number, position in enumerate(positions, start=1):
                yield stand, section, order, category, row, number, position, f'{slug}-r{row}-s{number:03d}.webp'


def build_photo(source, target):
    image = ImageOps.exif_transpose(Image.open(source)).convert('RGB')
    image.thumbnail(PHOTO_MAX_SIZE)
    image.save(target, 'WEBP', quality=PHOTO_QUALITY, method=4)  # saved without metadata


class Command(BaseCommand):
    help = 'Create the Nyayo handball court venue, its seats and prices, and optionally its seat photos.'

    def add_arguments(self, parser):
        parser.add_argument('--photos', help='Folder of original photos; builds the web photos into static/.')
        parser.add_argument('--no-event', action='store_true', help='Do not create a sample event.')

    def handle(self, *args, **opts):
        plan = list(seat_plan())
        if opts['photos']:
            self.build_photos(Path(opts['photos']), plan)
        self.create_venue(plan, not opts['no_event'])

    def build_photos(self, folder, plan):
        originals = sorted(p for p in folder.iterdir() if p.suffix.lower() == '.jpg')
        if len(originals) != 913:
            raise CommandError(f'Expected 913 originals in {folder}, found {len(originals)}.')
        out = Path(settings.BASE_DIR) / 'static' / PHOTO_DIR
        out.mkdir(parents=True, exist_ok=True)
        jobs = [(originals[item[6] - 1], out / item[7]) for item in plan if not (out / item[7]).exists()]
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda job: build_photo(*job), jobs))
        self.stdout.write(self.style.SUCCESS(f'Built {len(jobs)} photos in {out}'))

    @transaction.atomic
    def create_venue(self, plan, with_event):
        venue, created = Venue.objects.get_or_create(name=VENUE_NAME, defaults={
            'location': 'Nyayo National Stadium, Nairobi', 'capacity': len(plan),
            'description': 'Outdoor handball court with stands on two sides.',
        })
        if not created:
            self.stdout.write(self.style.WARNING(f'"{VENUE_NAME}" already exists; nothing changed.'))
            return
        categories = {name: SeatCategory.objects.create(venue=venue, name=name, price=price, description=text)
                      for name, (price, text) in CATEGORIES.items()}
        Seat.objects.bulk_create([
            Seat(venue=venue, stand=stand, section=section, section_order=order, category=categories[category],
                 row_number=row, seat_number=number, view_photo=f'{PHOTO_DIR}/{name}')
            for stand, section, order, category, row, number, _, name in plan
        ])
        self.stdout.write(self.style.SUCCESS(f'Created "{VENUE_NAME}" with {len(plan)} seats.'))
        if with_event:
            Event.objects.create(title='Handball Showcase Match', venue=venue, event_time=time(15, 0),
                                 event_date=date.today() + timedelta(days=14),
                                 description='Sample event for the Nyayo handball court.')
