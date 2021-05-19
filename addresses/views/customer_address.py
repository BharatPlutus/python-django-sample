from django.db.models import Q
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated

from common_config.document_link import CREATE_CUSTOMER_ADD_DOC, DOCUMENT_URL_TYPE
from common_config.generics import get_object_or_404
from common_config.logger.logging_handler import logger
from common_config.api_code import HTTP_201_CREATED, HTTP_OK, HTTP_400_BAD_REQUEST, \
    INVALID_ADDRESS_PAYLOAD, CUSTOMER_ADDRESS_CREATE_FAILURE
from common_config.api_message import UNEXPECTED_ERROR, ADD_CUSTOMER_ADDRESS, INVALID_PAGE_SIZE, \
    INVALID_PAGE_NUMBER, UPDATE_CUSTOMER_ADDRESS, NOT_FOUND_JSON_DATA, DELETE_CUSTOMER_ADDRESS, \
    EXTRA_QUERY_PARAMS, INVALID_BOOLEAN_FLAG, REQUIRED_PARAMS, INVALID_STORE_ID, BLANK_PARAM, INVALID_SORT_BY, \
    INVALID_CUSTOMER_ID, INVALID_CUSTOMER_CREATE_PAYLOAD
from utils.api_response import APIResponse, APIErrorResponse
from utils.permissions import IsAuthorized
from utils.pagination import Pagination

from stores.models.store import Store
from addresses.models.customer_address import CustomerAddress
from customers.models.customer import Customer
from addresses.serializers.customer_address import CustomerAddressCreateUpdateSerializer, CustomerAddressViewSerializer, \
    CustomerAddressListSerializer


class CustomerAddressesListCreateView(ListCreateAPIView):
    """
    An Api View which provides a method to add new customer address or view list customer addresses.
    Accepts the following GET/POST header parameters: access token
    Returns the success/fail message.
    """
    queryset = CustomerAddress.objects.all()
    serializer_class = CustomerAddressCreateUpdateSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('add_customeraddress', 'view_customeraddress',)
    pagination_class = Pagination
    query_filter_params = ["is_active", "include_deleted", "page", "page_size", "customer_id", "store_id", "sort_by",
                           "search"]

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

        store_id = self.params.get("store_id", None)

        if store_id is not None and not store_id.isnumeric():
            self.errors.setdefault("store_id", []).append(INVALID_STORE_ID.format(store_id))

        if store_id is not None and store_id.isnumeric():
            try:
                # validate store id is exits in database.
                Store.objects.get(pk=store_id)
            except Store.DoesNotExist as err:
                self.errors.setdefault("store_id", []).append(INVALID_STORE_ID.format(store_id))

        customer_id = self.params.get("customer_id", None)

        if customer_id is None:
            self.errors.setdefault("customer_id", []).append(REQUIRED_PARAMS)

        if customer_id is not None and not customer_id.isnumeric():
            self.errors.setdefault("customer_id", []).append(INVALID_CUSTOMER_ID.format(customer_id))

        if customer_id is not None and customer_id.isnumeric():
            try:
                # validate customer id is exits in database.
                Customer.objects.get(pk=customer_id)
            except Customer.DoesNotExist as err:
                self.errors.setdefault("customer_id", []).append(INVALID_CUSTOMER_ID.format(customer_id))

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
                    # validate view soft deleted object permission
                    IsAuthorized.has_include_deleted_permission(self.request, "view_customeraddress")

    def filter_queryset(self, params):

        filter_fields = ["store_id", "customer_id"]
        filter_kwargs = {'is_active': True}

        # create filter query params
        add_filter_kwargs = {key: params[key] for key in params.keys() if key in filter_fields}

        if "include_deleted" in params:
            del filter_kwargs['is_active']
        else:
            if "is_active" in params and params['is_active'] in ['False']:
                filter_kwargs['is_active'] = False

        filter_kwargs.update(add_filter_kwargs)
        query = Q()

        if "search" in params:
            query = Q(city__icontains=params['search']) | Q(state_id__name__icontains=params['search']) | \
                    Q(country_id__name__icontains=params['search']) | Q(zip_code__icontains=params['search']) | \
                    Q(street1__icontains=params['search']) | \
                    Q(customer_id__user__first_name__icontains=params['search']) | \
                    Q(customer_id__user__last_name__icontains=params['search'])

        for item in filter_kwargs:
            query = query & Q(**{item: filter_kwargs[item]})

        if "sort_by" in params and params['sort_by'] == "asc":
            return self.queryset.filter(query).order_by('id')

        return self.queryset.filter(query).order_by('id').reverse()

    def get(self, request, *args, **kwargs):
        """
        In this method validate request query parameters and filter and return customer address list.
        return success/error message.
        """
        # get all query params from request api endpoint
        self.params = request.query_params.copy()
        page_size = self.params.get('page_size', None)
        page = self.params.get('page', None)

        # validate customer params
        self.validate_query_param(page_size, page)

        if self.errors:
            return APIResponse(self.errors, HTTP_400_BAD_REQUEST)

        error_msg, status_code = None, None

        try:
            # search and filter customer addresses
            queryset = self.filter_queryset(self.params)
        except DjangoValidationError as err:
            error_msg, status_code = err.args[0], HTTP_400_BAD_REQUEST
        except Exception as e:
            logger.error("Unexpected error occurred :  %s.", e)
            error_msg, status_code = UNEXPECTED_ERROR, HTTP_400_BAD_REQUEST

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

        return self.paginator.generate_response(queryset, CustomerAddressListSerializer, request, is_pagination)

    @staticmethod
    def validate_customer(customer_id):
        # Perform the lookup filtering.
        filter_kwargs = {'pk': customer_id}

        # get query set objects
        customer_queryset = Customer.objects.all()

        # validate customer id and get object
        obj = get_object_or_404(customer_queryset, "customer_id", **filter_kwargs)
        return obj

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        In this method validate customer address from data and created new customer address.
        return success/error message.
        """
        request_data = request.data

        # create customer address serializers object
        serializer = self.serializer_class(data=request_data, context={'request': request, "validate_phone": True})

        # check customer address serializers is valid
        if not serializer.is_valid():
            return APIResponse(serializer.errors, HTTP_400_BAD_REQUEST)
            # return APIErrorResponse(data=serializer.errors, status=HTTP_400_BAD_REQUEST,
            #                         extra_info={"payload_code": INVALID_ADDRESS_PAYLOAD},
            #                         info={"url": CREATE_CUSTOMER_ADD_DOC, "type": DOCUMENT_URL_TYPE})

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # save customer address
            instance = serializer.create(serializer.validated_data)
        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            # roll back transaction if any exception occur while add new address
            transaction.savepoint_rollback(sid)
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)
            # return APIErrorResponse(message=INVALID_CUSTOMER_CREATE_PAYLOAD, status=HTTP_400_BAD_REQUEST,
            #                         extra_info={"payload_code": CUSTOMER_ADDRESS_CREATE_FAILURE},
            #                         info={"url": CREATE_CUSTOMER_ADD_DOC, "type": DOCUMENT_URL_TYPE})

        # convert model object into json
        data = CustomerAddressViewSerializer(instance).data
        data['message'] = ADD_CUSTOMER_ADDRESS
        return APIResponse(data, HTTP_201_CREATED)


class CustomerAddressesRetrieveUpdateDeleteView(RetrieveUpdateDestroyAPIView):
    """ActivityLogMixin,
    An Api View which provides a method to get/update/delete customer address.
    Accepts the following POST header parameters: access token
    Returns the success/fail message.
    """
    queryset = CustomerAddress.objects.all()
    serializer_class = CustomerAddressCreateUpdateSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('view_customeraddress', 'change_customeraddress', 'delete_customeraddress')
    lookup_field = 'pk'

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}

        # get object
        obj = get_object_or_404(queryset, "customer_address_id", **filter_kwargs)
        return obj

    def get(self, request, *args, **kwargs):
        # get address object
        customer_address_obj = self.get_object()

        # serialize store address objects
        serializer = CustomerAddressViewSerializer(customer_address_obj)

        return APIResponse(serializer.data, HTTP_OK)

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        # get customer address instance
        instance = self.get_object()
        request_data = request.data

        # validate request data body length is zero raise error message
        if len(request_data) == 0:
            return APIResponse({'message': NOT_FOUND_JSON_DATA}, HTTP_400_BAD_REQUEST)

        # create customer address serializers object
        serializer = self.serializer_class(data=request_data, partial=True, context={'request': request})

        # check customer address serializers is valid
        if not serializer.is_valid():
            return APIResponse(serializer.errors, HTTP_400_BAD_REQUEST)

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # update customer address
            instance = serializer.update(instance, serializer.validated_data)
        except Exception as e:
            logger.error("Unexpected error occurred :  %s.", e)
            # roll back transaction if any exception occur while update address
            transaction.savepoint_rollback(sid)
            return APIResponse({"message": UNEXPECTED_ERROR}, HTTP_400_BAD_REQUEST)

        # convert model object into json
        data = CustomerAddressViewSerializer(instance).data
        data['message'] = UPDATE_CUSTOMER_ADDRESS
        return APIResponse(data, HTTP_OK)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        """
        In this api method validate customer address id if valid delete customer address
        return success or error message.
        """
        # get customer address instance
        instance = self.get_object()

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # soft delete customer address
            instance.delete_address(request.user)
        except Exception as e:
            logger.error("Unexpected error occurred :  %s.", e)
            # roll back transaction if any exception occur while delete address
            transaction.savepoint_rollback(sid)
            return APIResponse({"message": UNEXPECTED_ERROR}, HTTP_400_BAD_REQUEST)

        return APIResponse({'message': DELETE_CUSTOMER_ADDRESS}, HTTP_OK)
