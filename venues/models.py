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
    
    class Meta:
        db_table = 'venues_seat'
        unique_together = ('venue', 'row_number', 'seat_number')
    
    def __str__(self):
        return f"{self.venue.name} - Row {self.row_number}, Seat {self.seat_number}"