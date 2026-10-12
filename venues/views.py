from rest_framework import viewsets

from users.permissions import IsAdminOrReadOnly

from .models import Venue
from .serializers import VenueSerializer


class VenueViewSet(viewsets.ModelViewSet):
    """/api/venues/ - public list/detail; only admins can create and edit (venues are shared by all organizers)."""
    queryset = Venue.objects.prefetch_related('categories').order_by('name')
    serializer_class = VenueSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name', 'location']
