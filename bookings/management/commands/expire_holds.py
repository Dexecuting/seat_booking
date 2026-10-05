from django.core.management.base import BaseCommand

from bookings.services import expire_stale_holds


class Command(BaseCommand):
    help = 'Mark pending bookings whose hold timer has run out as expired (run periodically).'

    def handle(self, *args, **opts):
        count = expire_stale_holds()
        self.stdout.write(self.style.SUCCESS(f'Expired {count} stale hold(s).'))
