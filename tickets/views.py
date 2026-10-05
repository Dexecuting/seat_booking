from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Ticket
from .serializers import TicketDetailSerializer, TicketSerializer
from .services import send_ticket_email


class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/tickets/              - my tickets
    GET  /api/tickets/<id>/         - one ticket, including its QR code image
    POST /api/tickets/<id>/resend/  - email the ticket again
    """
    filterset_fields = ['is_used', 'booking__event']

    def get_queryset(self):
        return (Ticket.objects.filter(booking__fan=self.request.user)
                .select_related('booking__event__venue', 'booking__seat__category', 'booking__fan')
                .order_by('booking__event__event_date', 'id'))

    def get_serializer_class(self):
        return TicketSerializer if self.action == 'list' else TicketDetailSerializer

    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        if not send_ticket_email(self.get_object()):
            return Response({'detail': 'Could not send the email. Check the email on your profile.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Ticket sent to your email.'})
