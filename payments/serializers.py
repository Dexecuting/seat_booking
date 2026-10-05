from rest_framework import serializers

from bookings.models import Booking
from users.serializers import normalize_kenyan_phone

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    booking_status = serializers.CharField(source='booking.status', read_only=True)

    class Meta:
        model = Payment
        fields = ('id', 'booking', 'booking_status', 'amount', 'phone', 'status',
                  'mpesa_reference', 'result_desc', 'payment_date', 'created_at')
        read_only_fields = fields


class StartPaymentSerializer(serializers.Serializer):
    booking = serializers.PrimaryKeyRelatedField(queryset=Booking.objects.none())
    phone = serializers.CharField(required=False, allow_blank=True,
                                  help_text="M-Pesa number to charge; defaults to the fan's phone.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Fans can only pay for their own bookings.
        user = self.context['request'].user
        self.fields['booking'].queryset = (Booking.objects.filter(fan=user)
                                           .select_related('seat__category'))

    def validate_phone(self, value):
        return normalize_kenyan_phone(value) if value else value

    def validate(self, attrs):
        if not attrs.get('phone'):
            user_phone = self.context['request'].user.phone
            if not user_phone:
                raise serializers.ValidationError({'phone': 'Enter the M-Pesa number to charge.'})
            attrs['phone'] = normalize_kenyan_phone(user_phone)
        return attrs
