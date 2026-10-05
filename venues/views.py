from rest_framework import viewsets

from users.permissions import IsOrganizerOrReadOnly

from .models import Venue
from .serializers import VenueSerializer


class VenueViewSet(viewsets.ModelViewSet):
    """/api/venues/ - public list/detail; organizers can create and edit."""
    queryset = Venue.objects.prefetch_related('categories').order_by('name')
    serializer_class = VenueSerializer
    permission_classes = [IsOrganizerOrReadOnly]
    search_fields = ['name', 'location']
