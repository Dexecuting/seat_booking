from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsGateStaff, IsOrganizer

from .models import GateEntry
from .serializers import GateEntrySerializer, ScanSerializer, scan_result_data
from .validators import validate_ticket


class ScanView(APIView):
    """
    POST /api/gates/scan/ {"token": "<QR contents>", "event": 3}
    Always returns 200 with {"allowed": true/false, "reason": ...} for the scanner to display.
    """
    permission_classes = [IsGateStaff]

    def post(self, request):
        serializer = ScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = validate_ticket(
            serializer.validated_data['token'],
            scanned_by=request.user,
            event_id=serializer.validated_data.get('event'),
        )
        return Response(scan_result_data(result))


class GateEntryListView(generics.ListAPIView):
    """GET /api/gates/entries/?ticket__booking__event=3&entry_allowed=false - scan log for organizers."""
    permission_classes = [IsOrganizer]
    serializer_class = GateEntrySerializer
    filterset_fields = ['entry_allowed', 'ticket__booking__event']
    queryset = (GateEntry.objects
                .select_related('scanned_by', 'ticket__booking__event')
                .order_by('-scan_time'))
