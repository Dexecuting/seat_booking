from rest_framework import serializers

from .models import Venue, SeatCategory


class SeatCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SeatCategory
        fields = ('id', 'name', 'price', 'description')


class VenueSerializer(serializers.ModelSerializer):
    categories = SeatCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Venue
        fields = ('id', 'name', 'location', 'capacity', 'description', 'categories')
