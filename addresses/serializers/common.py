from rest_framework import serializers
from addresses.models.base import City, State, Country


class CountryViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ('id', 'name',)


class CityViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ('id', 'name',)


class StateListSerializer(serializers.ModelSerializer):
    country = CountryViewSerializer(source="country_id")

    class Meta:
        model = State
        fields = ('id', 'name', "country")


class CityListSerializer(serializers.ModelSerializer):
    state = StateListSerializer(source="state_id")

    class Meta:
        model = City
        fields = ('id', 'name', "state")
