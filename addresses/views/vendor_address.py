from django.db.models import Q
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated

from authentication.views.helper import validate_vendor_signup_steps
from common_config.logger.logging_handler import logger
from common_config.api_code import HTTP_OK, HTTP_400_BAD_REQUEST, HTTP_201_CREATED
from common_config.api_message import UNEXPECTED_ERROR, EXTRA_QUERY_PARAMS, INVALID_PAGE_SIZE, NOT_FOUND_JSON_DATA,\
    INVALID_PAGE_NUMBER, BLANK_PARAM, INVALID_SORT_BY, INVALID_BOOLEAN_FLAG, REQUIRED_PARAMS, DELETE_VENDOR_ADDRESS, \
    UPDATE_VENDOR_ADDRESS, ADD_VENDOR_ADDRESS, INVALID_VENDOR_ID
from common_config.generics import get_object_or_404

from utils.api_response import APIResponse
from utils.permissions import IsAuthorized
from utils.pagination import Pagination

from vendors.models.vendor import Vendor
from addresses.models.vendor_address import VendorAddress
from addresses.serializers.vendor_address import VendorAddressListSerializer, VendorAddressCreateUpdateSerializer, \
    VendorAddressViewSerializer


class VendorAddressesListCreateView(ListCreateAPIView):
    """
    An Api View which provides a method to add new vendor address or view list vendor addresses.
    Accepts the following POST header parameters: access token
    Returns the success/fail message.
    """

    queryset = VendorAddress.objects.all()
    serializer_class = VendorAddressCreateUpdateSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('add_vendoraddress', 'view_vendoraddress',)
    pagination_class = Pagination
    query_filter_params = ["is_active", "include_deleted", "page", "page_size", "vendor_id", "sort_by", "search"]

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

        vendor_id = self.params.get("vendor_id", None)

        if vendor_id is None:
            self.errors.setdefault("vendor_id", []).append(REQUIRED_PARAMS)

        if vendor_id is not None and not vendor_id.isnumeric():
            self.errors.setdefault("vendor_id", []).append(INVALID_VENDOR_ID.format(vendor_id))

        if vendor_id is not None and vendor_id.isnumeric():
            try:
                # validate vendor id is exits in database.
                Vendor.objects.get(pk=vendor_id)
            except Vendor.DoesNotExist as err:
                self.errors.setdefault("vendor_id", []).append(INVALID_VENDOR_ID.format(vendor_id))

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
                    IsAuthorized.has_include_deleted_permission(self.request, "view_vendoraddress")

    def filter_queryset(self, params):
        # create filter query params
        filter_kwargs = {'is_active': True, "vendor_id": params['vendor_id']}

        if "include_deleted" in params:
            del filter_kwargs['is_active']
        else:
            if "is_active" in params and params['is_active'] in ['False']:
                filter_kwargs['is_active'] = False

        query = Q()

        if "search" in params:
            search = params['search']
            query = Q(city__icontains=search) | Q(state_id__name__icontains=search) | \
                    Q(country_id__name__icontains=search) | Q(zip_code__icontains=search) | \
                    Q(street1__icontains=search) | Q(street2__icontains=search) | Q(label__icontains=search)

        for item in filter_kwargs:
            query = query & Q(**{item: filter_kwargs[item]})

        if "sort_by" in params and params['sort_by'] == "asc":
            return self.queryset.filter(query).order_by('id')

        return self.queryset.filter(query).order_by('id').reverse()

    def get(self, request, *args, **kwargs):
        """
        In this method validate request query parameters and filter and return vendor address list.
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
            # search and filter addresses
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

        return self.paginator.generate_response(queryset, VendorAddressListSerializer, request, is_pagination)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        In this method validate store address from data and created new store address.
        return success/error message.
        """
        request_data = request.data

        # create address serializers object
        serializer = self.serializer_class(data=request_data, context={'request': request})

        # check address serializers is valid
        if not serializer.is_valid():
            return APIResponse(serializer.errors, HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # save vendor address
            instance = serializer.create(validated_data)
        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            # roll back transaction if any exception occur while add new address
            transaction.savepoint_rollback(sid)
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        # convert model object into json
        data = VendorAddressViewSerializer(instance).data
        data['message'] = ADD_VENDOR_ADDRESS

        if "vendor_id" in validated_data:
            registration_steps = validate_vendor_signup_steps(validated_data['vendor_id'])
            if registration_steps:
                data['registration_steps'] = registration_steps

        return APIResponse(data, HTTP_201_CREATED)


class VendorAddressesRetrieveUpdateDeleteView(RetrieveUpdateDestroyAPIView):
    """
    An Api View which provides a method to get/update/delete vendor address details.
    Accepts the following GET/PUT/DELETE header parameters: access token
    Returns the success/fail message.
    """
    queryset = VendorAddress.objects.all()
    serializer_class = VendorAddressCreateUpdateSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('change_vendoraddress', 'view_vendoraddress', 'delete_vendoraddress',)
    lookup_field = 'pk'

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}

        # get object
        obj = get_object_or_404(queryset, "vendor_address_id", **filter_kwargs)
        return obj

    def get(self, request, *args, **kwargs):
        """
        In this api method validate address id if valid
        return address details with success message else error message.
       """

        # validate and get object
        instance = self.get_object()

        # convert model object into json
        data = VendorAddressViewSerializer(instance).data

        return APIResponse(data, HTTP_OK)

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        """
        In this api method validate address id and json data, if valid update existing address.
        return success/error message.
        """
        payload = request.data
        instance = self.get_object()

        # validate request data body length is zero raise error message
        if len(payload) == 0:
            return APIResponse({'message': NOT_FOUND_JSON_DATA}, HTTP_400_BAD_REQUEST)

        # create store address serializers object
        serializer = self.serializer_class(data=payload, partial=True, context={'request': request})

        # check vendor address serializers is valid
        if not serializer.is_valid():
            return APIResponse(serializer.errors, HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # update address
            instance = serializer.update(instance, validated_data)
        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err.args[0])
            # roll back transaction if any exception occur while update address
            transaction.savepoint_rollback(sid)
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        # convert model object into json
        data = VendorAddressViewSerializer(instance).data
        data['message'] = UPDATE_VENDOR_ADDRESS

        return APIResponse(data, HTTP_OK)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        """
        In this api method validate address id if valid delete address
        return success or error message.
        """
        # validate address id and get object
        instance = self.get_object()

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # soft delete address
            instance.delete_address(request.user)
        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            # roll back transaction if any exception occur while delete address
            transaction.savepoint_rollback(sid)
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        return APIResponse({"message": DELETE_VENDOR_ADDRESS}, HTTP_OK)
