import re

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User, Fan


def normalize_kenyan_phone(value):
    """
    Accept 07XXXXXXXX, 01XXXXXXXX, +2547XXXXXXXX or 2547XXXXXXXX and return 2547XXXXXXXX,
    the format the M-Pesa STK Push API expects.
    """
    digits = re.sub(r'[\s\-]', '', value).lstrip('+')
    if re.fullmatch(r'0[17]\d{8}', digits):
        digits = '254' + digits[1:]
    if not re.fullmatch(r'254[17]\d{8}', digits):
        raise serializers.ValidationError('Enter a valid Kenyan phone number, e.g. 0712345678.')
    return digits


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'phone', 'role')
        read_only_fields = ('id', 'username', 'role')

    def validate_phone(self, value):
        return normalize_kenyan_phone(value) if value else value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value


class RegisterSerializer(serializers.ModelSerializer):
    """Self-registration always creates a fan; organizers/admins are set up by an administrator."""

    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(required=True, max_length=15)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'phone', 'password')
        read_only_fields = ('id',)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate_phone(self, value):
        return normalize_kenyan_phone(value)

    def validate(self, attrs):
        user = User(**{k: v for k, v in attrs.items() if k != 'password'})
        validate_password(attrs['password'], user)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(role='fan', **validated_data)
        Fan.objects.create(user=user)
        return user


class TokenWithRoleSerializer(TokenObtainPairSerializer):
    """Login: adds username and role to the token so the frontend can tailor the UI."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data
