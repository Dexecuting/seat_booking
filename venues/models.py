from django.db import models


class Venue(models.Model):
    """Sports venue information"""
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    capacity = models.IntegerField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'venues_venue'
    
    def __str__(self):
        return self.name


class SeatCategory(models.Model):
    """Seat price categories (VIP, Regular, Student)"""
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'venues_seatcategory'
        verbose_name_plural = 'Seat Categories'
    
    def __str__(self):
        return f"{self.venue.name} - {self.name}"


class Seat(models.Model):
    """Individual seat. Availability is per event, so it is derived from Booking, not stored here."""
    
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='seats')
    row_number = models.IntegerField()
    seat_number = models.IntegerField()
    category = models.ForeignKey(SeatCategory, on_delete=models.CASCADE)
    # Layout for venues with stands either side of a court; blank for a simple single-stand grid.
    stand = models.CharField(max_length=30, blank=True, help_text='Which stand the seat is in, e.g. first or second.')
    section = models.CharField(max_length=60, blank=True, help_text='Named part of the stand, e.g. Foldable red.')
    section_order = models.PositiveSmallIntegerField(default=0, help_text='Left-to-right order of sections on the map.')
    view_photo = models.CharField(max_length=255, blank=True, help_text='Static file path of the photo taken from this seat.')
    
    class Meta:
        db_table = 'venues_seat'
        unique_together = ('venue', 'stand', 'section', 'row_number', 'seat_number')
    
    def __str__(self):
        return f"{self.venue.name} - {self.label}"

    @property
    def label(self):
        """How the seat is named to people, e.g. 'Foldable red, Row 2, Seat 5'."""
        place = f'Row {self.row_number}, Seat {self.seat_number}'
        return f'{self.section}, {place}' if self.section else place