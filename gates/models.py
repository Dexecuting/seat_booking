from django.db import models
from tickets.models import Ticket


class GateEntry(models.Model):
    """Gate entry log for each ticket scan"""
    
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='gate_entries')
    scan_time = models.DateTimeField(auto_now_add=True)
    entry_allowed = models.BooleanField()
    notes = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'gates_gateentry'
    
    def __str__(self):
        return f"Gate Entry: {self.ticket.qr_token[:10]}... at {self.scan_time}"