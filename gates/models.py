from django.conf import settings
from django.db import models
from tickets.models import Ticket


class GateEntry(models.Model):
    """Log of every ticket scan, allowed or denied (including unrecognised QR codes)."""
    
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='gate_entries',
                               null=True, blank=True)
    scanned_token = models.CharField(max_length=255, blank=True)
    scanned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='gate_scans')
    scan_time = models.DateTimeField(auto_now_add=True)
    entry_allowed = models.BooleanField()
    notes = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'gates_gateentry'
    
    def __str__(self):
        result = 'allowed' if self.entry_allowed else 'denied'
        return f"Gate Entry: {self.scanned_token[:10]}... {result} at {self.scan_time}"
