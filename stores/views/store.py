from django.db.models import Q
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, RetrieveAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated

from authentication.views.helper import validate_store_on_boarding_steps
from common_config.api_code import HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_OK, HTTP_500_INTERNAL_SERVER_ERROR
from common_config.api_message import UNEXPECTED_ERROR, ADD_STORE, UPDATE_STORE, INVALID_PAGE_SIZE, \
    NOT_FOUND_JSON_DATA, DELETE_STORE, EXTRA_QUERY_PARAMS, INVALID_PAGE_NUMBER, DUPLICATE_STORE_SUBDOMAIN, \
    AVAILABLE_STORE_SUBDOMAIN, INVALID_BOOLEAN_FLAG, BLANK_PARAM, INVALID_SORT_BY, DUPLICATE_WHITE_LABEL_DOMAIN, \
    AVAILABLE_STORE_WHITE_LABEL_DOMAIN, GET_STARTED_STORE
from common_config.constant import DEFAULT_PORTAL_LOGO
from common_config.logger.logging_handler import logger
from common_config.generics import get_object_or_404
from users.utils.permission import store_access_modules
from utils.api_response import APIResponse
from utils.permissions import IsAuthorized
from utils.pagination import Pagination

from stores.models.store import Store
from stores.serializers.store import StoreCreateSerializer, StoreViewSerializer, StoreUpdateSerializer, \
    StoreListSerializer, StoreGetStartedSerializer
from stores.task.store_registration import store_registration_task


class StoreListCreateView(ListCreateAPIView):
    """
    An Api View which provides a method to add new store or view list stores.
    Accepts the following GET/POST header parameters: access token
    Returns the success/fail message.
    """
    queryset = Store.objects.all()
    serializer_class = StoreCreateSerializer
    pagination_class = Pagination
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('add_store', 'list_store')
    query_filter_params = ["is_active", "include_deleted", "page", "page_size", "search", "sort_by"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.errors = dict()
        self.params = dict()

    def validate_query_param(self, page_size, page):
        # check pre define query parameter if contain extra query param then raise error message
        if len(self.params) > 0 and not all(key in self.query_filter_params for key in self.params.keys()):
            extra_param = [key for key in self.params if key not in self.query_filter_params]
            self.errors.setdefault("message", []).append(EXTRA_QUERY_PARAMS.format(extra_param))

        # check page size must  number
        if "page_size" in self.params and not page_size.isnumeric():
            self.errors.setdefault("page_size", []).append(INVALID_PAGE_SIZE)

        if "page" in self.params and not page.isnumeric():
            self.errors.setdefault("page", []).append(INVALID_PAGE_NUMBER)

        if "is_active" in self.params:
            try:
                eval(self.params['is_active'])
            except Exception as err:
                self.errors.setdefault("is_active", []).append(
                    INVALID_BOOLEAN_FLAG.format("is_active", self.params['is_active']))
        if "sort_by" in self.params:
            if self.params['sort_by'] == "":
                self.errors.setdefault("sort_by", []).append(BLANK_PARAM)
            elif self.params['sort_by'].lower() not in ["asc", "desc"]:
                self.errors.setdefault("sort_by", []).append(INVALID_SORT_BY.format(self.params['sort_by']))

        if "search" in self.params and self.params['search'] == "":
            self.errors.setdefault("search", []).append(BLANK_PARAM)

        if "include_deleted" in self.params:
            try:
                eval(self.params['include_deleted'])
            except Exception as err:
                self.errors.setdefault("include_deleted", []).append(
                    INVALID_BOOLEAN_FLAG.format("include_deleted", self.params['include_deleted']))
            else:
                if not self.errors:
                    # validate view soft deleted object view permission
                    IsAuthorized.has_include_deleted_permission(self.request, "list_store")

    def filter_queryset(self, params):
        # create filter query params
        filter_kwargs = {'is_active': True}
        if "is_active" in params and params['is_active'] in ['False']:
            filter_kwargs['is_active'] = False

        query = Q()
        if "search" in params:
            query = Q(name__icontains=params['search'])

        for item in filter_kwargs:
            query = query & Q(**{item: filter_kwargs[item]})

        if "sort_by" in params and params['sort_by'] == "asc":
            return self.queryset.filter(query).order_by('created_on')

        return self.queryset.filter(query).order_by('created_on').reverse()

    def get(self, request, *args, **kwargs):
        """
        In this method validate request query parameters and filter and return store list.
        return success/error message.
        """
        self.params = request.query_params.copy()
        page_size = self.params.get('page_size', None)
        page = self.params.get('page', None)

        # validate sales order params
        self.validate_query_param(page_size, page)

        if self.errors:
            return APIResponse(self.errors, HTTP_400_BAD_REQUEST)

        error_msg, status_code = None, None

        try:
            # filter and get all store based on query params
            queryset = self.filter_queryset(self.params)
        except DjangoValidationError as err:
            error_msg, status_code = err.args[0], HTTP_400_BAD_REQUEST
        except Exception as e:
            logger.error("Unexpected error occurred :  %s.", e)
            error_msg, status_code = UNEXPECTED_ERROR, HTTP_500_INTERNAL_SERVER_ERROR

        if error_msg is not None:
            return APIResponse({"message": error_msg}, status_code)

        is_pagination = False

        # set api request page number
        if page is not None:
            self.paginator.page = page
            is_pagination = True

            # set request api page size number
            if page_size is None:
                page_size = 10

            self.paginator.page_size = page_size

        return self.paginator.generate_response(queryset, StoreListSerializer, request, is_pagination)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        In this method validate store from data and created new store.
        return success/error message.
        """
        request_data = request.data

        if 'logo' not in request_data:
            request_data['logo'] = DEFAULT_PORTAL_LOGO

        # create store serializers object
        serializer = self.serializer_class(data=request_data, context={'request': request})

        # check store serializers is valid
        if not serializer.is_valid():
            return APIResponse(serializer.errors, HTTP_400_BAD_REQUEST)

        # get last transaction save point id
        sid = transaction.savepoint()

        validated_data = serializer.validated_data

        try:
            # add new store
            instance = serializer.create(validated_data)
        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            # roll back transaction if any exception occur while add store
            transaction.savepoint_rollback(sid)
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        # convert model instance into json object
        data = StoreViewSerializer(instance).data
        data['message'] = ADD_STORE

        system_payload = data.copy()
        system_payload['password'] = request_data['user']['password']

        if "price_group_id" in request_data:
            system_payload['price_group_id'] = request_data['price_group_id']

        # system user send an email to store owner and assign store services
        store_registration_task.delay(system_payload)

        return APIResponse(data, HTTP_201_CREATED)


class StoreRetrieveUpdateDeleteView(RetrieveUpdateDestroyAPIView):
    """
    An Api View which provides a method to get, update and delete store.
    Accepts the following GET/PUT/DELETE header parameters: access token
    Returns the success/fail message.
    """
    queryset = Store.objects.all()
    serializer_class = StoreUpdateSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('change_store', 'view_store', 'delete_store')
    lookup_field = 'pk'

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}

        # get object
        obj = get_object_or_404(queryset, "store_id", **filter_kwargs)

        return obj

    def get(self, request, *args, **kwargs):
        """
        In this api method validate store_id if valid
        return store details with success message else error message.
        """

        # get store object
        storeObj = self.get_object()

        # create store serializers object
        serializer = StoreViewSerializer(storeObj)

        return APIResponse(serializer.data, HTTP_OK)

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        # get store object
        instance = self.get_object()

        request_data = request.data

        # validate request data body length is zero raise error message
        if len(request_data) == 0:
            return APIResponse({'message': NOT_FOUND_JSON_DATA}, HTTP_400_BAD_REQUEST)

        # create store serializers object
        serializer = self.serializer_class(data=request_data, context={'request': request}, partial=True)

        # check store serializers is valid
        if not serializer.is_valid():
            return APIResponse(serializer.errors, HTTP_400_BAD_REQUEST)

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # update existing store
            instance = serializer.update(instance, serializer.validated_data)
        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            # roll back transaction if any exception occur while update store
            transaction.savepoint_rollback(sid)

            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        # convert model instance into json object
        data = StoreViewSerializer(instance).data
        data['message'] = UPDATE_STORE

        return APIResponse(data, HTTP_OK)

    def delete(self, request, *args, **kwargs):
        # get store object
        storeInstance = self.get_object()

        try:
            # soft delete store
            storeInstance.delete()
        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            return APIResponse({"message": err.args[0]}, HTTP_500_INTERNAL_SERVER_ERROR)

        return APIResponse({'message': DELETE_STORE}, HTTP_OK)


class StoreSubDomain(RetrieveAPIView):
    """
        An Api View which provides a method to get validate store subdomain.
        Accepts the following GET header parameters: access token
        Returns the success/fail message.
    """
    queryset = Store.objects.all()
    serializer_class = StoreUpdateSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('view_store',)
    lookup_field = 'subdomain'

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}

        stores = queryset.filter(**filter_kwargs)

        if stores:
            return False

        return True

    def get(self, request, *args, **kwargs):

        response_code = HTTP_OK
        data = {'subdomain': [AVAILABLE_STORE_SUBDOMAIN]}

        if not self.get_object():
            response_code = HTTP_400_BAD_REQUEST
            data['subdomain'] = [DUPLICATE_STORE_SUBDOMAIN.format(self.kwargs['subdomain'])]

        return APIResponse(data, response_code)


class StoreWhiteLabelDomain(RetrieveAPIView):
    """
        An Api View which provides a method to get validate store white label domain.
        Accepts the following GET header parameters: access token
        Returns the success/fail message.
    """
    queryset = Store.objects.all()
    serializer_class = StoreUpdateSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('view_store',)
    lookup_field = 'white_label_domain'

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}

        stores = queryset.filter(**filter_kwargs)

        if stores:
            return False

        return True

    def get(self, request, *args, **kwargs):

        response_code = HTTP_OK
        data = {'white_label_domain': [AVAILABLE_STORE_WHITE_LABEL_DOMAIN]}

        if not self.get_object():
            response_code = HTTP_400_BAD_REQUEST
            data['white_label_domain'] = [DUPLICATE_WHITE_LABEL_DOMAIN.format(self.kwargs['white_label_domain'])]

        return APIResponse(data, response_code)


class StoreGetStartedView(UpdateAPIView):
    """
          An Api View which provides a method to put complete on boarding process.
          Accepts the following PUT header parameters: access token
          Returns the success/fail message.
    """
    queryset = Store.objects.all()
    serializer_class = StoreGetStartedSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('change_store',)
    lookup_field = 'pk'

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}

        # get object
        obj = get_object_or_404(queryset, "store_id", **filter_kwargs)

        return obj

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        # get store object
        instance = self.get_object()

        # get last transaction save point id
        sid = transaction.savepoint()

        serializer = self.serializer_class(context={'request': request})

        try:
            # update existing store
            instance = serializer.get_started(instance)
        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            # roll back transaction if any exception occur while update store
            transaction.savepoint_rollback(sid)
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        # convert model instance into json object
        data = StoreViewSerializer(instance).data
        data['message'] = GET_STARTED_STORE

        # get all on-boarding steps
        on_boarding_steps, subscription_obj = validate_store_on_boarding_steps(instance)

        # get all module
        moduleJson = store_access_modules

        if subscription_obj:
            access_modules = list(subscription_obj[0].plan_id.access_modules.keys())

            if "1" in access_modules and "2" in access_modules and len(access_modules) == 2:
                moduleJson = {key: value1 for key, value1 in moduleJson.items() if key not in [8, 9]}
            elif "1" in access_modules and "2" in access_modules and "3" in access_modules and len(access_modules) == 3:
                moduleJson = {key: value1 for key, value1 in moduleJson.items() if key not in [8]}

        data['on_boarding_steps'] = on_boarding_steps
        data['access_modules'] = moduleJson

        return APIResponse(data, HTTP_OK)
