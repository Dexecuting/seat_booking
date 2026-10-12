from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsOrganizer, is_admin
from venues.models import Venue

from .services import PERIOD_CHOICES, build_dashboard


class DashboardView(APIView):
    """
    GET /api/reports/dashboard/?days=30&venue=1
      days:  7 | 30 | 90 | 365 | all   (sales period, default 30)
      venue: optional venue id - narrows everything and enables the seat heatmap
    Organizers see only the events they organise; admins see everything.
    """
    permission_classes = [IsOrganizer]

    def get(self, request):
        days = request.query_params.get('days', '30')
        if days not in PERIOD_CHOICES:
            days = '30'
        venue_id = request.query_params.get('venue')
        organizer = None if is_admin(request.user) else request.user
        data = build_dashboard(days, int(venue_id) if venue_id and venue_id.isdigit() else None, organizer)
        venues = Venue.objects.order_by('name')
        if organizer:
            venues = venues.filter(events__organizer=organizer).distinct()
        data['venues'] = list(venues.values('id', 'name'))
        data['scope'] = 'mine' if organizer else 'all'
        return Response(data)
