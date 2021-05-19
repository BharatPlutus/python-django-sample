from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from addresses.models.base import Country, State, City
from addresses.serializers.common import CountryViewSerializer, StateListSerializer, CityViewSerializer, \
    CityListSerializer
from utils.api_response import APIResponse
from common_config.api_code import HTTP_OK
from common_config.generics import get_object_or_404


class CountryListView(ListAPIView):
    """
    An Api View which provides a method to get country list .
    Accepts the following GET header parameters: access token
    Returns the success/fail message.
    """
    queryset = Country.objects.all()
    serializer_class = CountryViewSerializer
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.serializer_class(queryset, many=True)
        return APIResponse(serializer.data, HTTP_OK)


class StateListView(ListAPIView):
    """
    An Api View which provides a method to get state list by country id.
    Accepts the following GET header parameters: access token
    Returns the success/fail message.
    """
    queryset = State.objects.all()
    serializer_class = StateListSerializer
    permission_classes = (AllowAny,)
    lookup_field = "country_id"

    def get_object(self):
        # Perform the lookup filtering.
        filter_kwargs = {'pk': self.kwargs[self.lookup_field]}
        # get query set objects
        queryset = Country.objects.all()
        # get object
        obj = get_object_or_404(queryset, "country_id", **filter_kwargs)

        return obj

    def get(self, request, *args, **kwargs):
        # get all query params from request api endpoint
        params = request.query_params

        # validate state id and get object
        country_obj = self.get_object()

        query_filter = {"country_id": country_obj.id}

        if "name" in params:
            query_filter['name__icontains'] = params['name']

        # filter and get all state by country id
        stateObj = State.objects.filter(**query_filter)

        # create state serializers object
        serializer = self.serializer_class(stateObj, many=True)

        return APIResponse(serializer.data, HTTP_OK)


class CityListView(ListAPIView):
    """
    An Api View which provides a method to get city list by state id.
    Accepts the following GET header parameters: access token
    Returns the success/fail message.
    """
    queryset = City.objects.all()
    serializer_class = CityViewSerializer
    permission_classes = (AllowAny,)
    lookup_field = "state_id"

    def get_object(self):
        # Perform the lookup filtering.
        filter_kwargs = {'pk': self.kwargs[self.lookup_field]}

        # get query set objects
        queryset = State.objects.all()
        # get object
        obj = get_object_or_404(queryset, "state_id", **filter_kwargs)

        return obj

    def get(self, request, *args, **kwargs):
        # validate state id and get object
        state = self.get_object()

        # filter and get all city by state id
        cityObj = City.objects.filter(state_id=state.id)

        # create city serializers object
        serializer = self.serializer_class(cityObj, many=True)

        return APIResponse(serializer.data, HTTP_OK)


class FilterCityListView(ListAPIView):
    """
    An Api View which provides a method to get city list by name.
    Accepts the following GET header parameters: access token
    Returns the success/fail message.
    """
    queryset = City.objects.all()
    serializer_class = CityListSerializer
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        # get all query params from request api endpoint
        params = request.query_params

        query_filter = {}
        if "name" in params:
            query_filter['name__icontains'] = params['name']

        # filter and get all city by state id
        cityObj = City.objects.filter(**query_filter)

        # create city serializers object
        serializer = self.serializer_class(cityObj, many=True)

        return APIResponse(serializer.data, HTTP_OK)
