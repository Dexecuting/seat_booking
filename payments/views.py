import logging
import secrets

from django.conf import settings
from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment
from .serializers import PaymentSerializer, StartPaymentSerializer
from .services import PaymentError, process_stk_callback, refresh_from_daraja, start_payment

logger = logging.getLogger(__name__)


class PaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    POST /api/payments/  {"booking": 12, "phone": "0712345678"}  - send M-Pesa PIN prompt
    GET  /api/payments/<id>/                                     - poll payment status
    POST /api/payments/<id>/refresh/                             - ask M-Pesa for the result
    GET  /api/payments/                                          - my payments
    """
    serializer_class = PaymentSerializer
    filterset_fields = ['status', 'booking']

    def get_queryset(self):
        return (Payment.objects.filter(booking__fan=self.request.user)
                .select_related('booking').order_by('-created_at'))

    def create(self, request, *args, **kwargs):
        serializer = StartPaymentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            payment = start_payment(**serializer.validated_data)
        except PaymentError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        payment = refresh_from_daraja(self.get_object())
        return Response(PaymentSerializer(payment).data)


class MpesaCallbackView(APIView):
    """
    POST /api/payments/mpesa/callback/<token>/ - called by Safaricom, not by users.
    The secret token in the URL stops anyone else from posting fake 'payment succeeded' results.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, token):
        expected = settings.DARAJA_CALLBACK_TOKEN
        if not expected or not secrets.compare_digest(token, expected):
            raise Http404
        logger.info('M-Pesa callback: %s', request.data)
        process_stk_callback(request.data)
        # Always acknowledge, otherwise Safaricom keeps retrying.
        return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})
