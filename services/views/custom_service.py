from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView

from common_config.api_code import HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_OK, HTTP_500_INTERNAL_SERVER_ERROR
from common_config.api_message import ADD_CUSTOM_SERVICE, EXTRA_QUERY_PARAMS, INVALID_PAGE_SIZE, INVALID_PAGE_NUMBER, \
    INVALID_BOOLEAN_FLAG, BLANK_PARAM, INVALID_SORT_BY, INVALID_SORT_BY_FIELD_PARAM, REQUIRED_PARAMS, INVALID_VENDOR_ID, \
    INVALID_CUSTOM_SERVICE_ID, UPDATE_CUSTOM_SERVICE, DELETE_CUSTOM_SERVICE
from common_config.http import Http404
from common_config.logger.logging_handler import logger
from utils.api_response import APIResponse
from utils.permissions import IsAuthorized
from utils.pagination import Pagination

from services.models.custom_service import CustomService
from services.serializers.custom_service import CustomServiceViewSerializer, CustomServiceCreateSerializer, \
    CustomServiceListSerializer, CustomServiceUpdateSerializer
from vendors.models.vendor import Vendor


class CustomServiceListCreateView(ListCreateAPIView):
    """
    An Api View which provides a method to add new or view list custom services.
    Accepts the following GET/POST header parameters: access token
    Returns the success/fail message.
    """
    queryset = CustomService.objects.all()
    serializer_class = CustomServiceCreateSerializer
    pagination_class = Pagination
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('add_customservice', 'list_customservice',)
    query_filter_params = ["is_active", "include_deleted", "page", "page_size", "sort_by", "search", "sort_by_field",
                           "vendor_id"]

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

        if "sort_by_field" in self.params and self.params['sort_by_field'] not in ["name", "description",
                                                                                   "short_description", "price"]:
            self.errors.setdefault("sort_by_field", []).append(INVALID_SORT_BY_FIELD_PARAM)

        if "sort_by_field" in self.params and "sort_by" not in self.params:
            self.errors.setdefault("sort_by", []).append(REQUIRED_PARAMS)

        if "include_deleted" in self.params:
            try:
                eval(self.params['include_deleted'])
            except Exception as err:
                self.errors.setdefault("include_deleted", []).append(
                    INVALID_BOOLEAN_FLAG.format("include_deleted", self.params['include_deleted']))
            else:
                if not self.errors:
                    # validate view soft deleted object view permission
                    IsAuthorized.has_include_deleted_permission(self.request, "list_customservice")

    def filter_queryset(self, params):
        filter_kwargs = {'is_active': True, "vendor_id": params['vendor_id']}
        if "is_active" in params and params['is_active'] in ['False']:
            filter_kwargs['is_active'] = False

        if "sort_by_field" in params:
            if params['sort_by_field'] == "name":
                sort_by_field = "name"
            elif params['sort_by_field'] == "description":
                sort_by_field = "description"
            elif params['sort_by_field'] == "short_description":
                sort_by_field = "short_description"
            else:
                sort_by_field = "price"
        else:
            sort_by_field = "created_on"

        query = Q()

        if "search" in params:
            query = Q(name__icontains=params['search']) | Q(description__icontains=params['search']) | \
                    Q(short_description__icontains=params['search']) | Q(price__icontains=params['search'])

        for item in filter_kwargs:
            query = query & Q(**{item: filter_kwargs[item]})

        if "sort_by" in params and params['sort_by'] == "asc":
            return self.queryset.filter(query).order_by(sort_by_field)

        return self.queryset.filter(query).order_by(sort_by_field).reverse()

    def get(self, request, *args, **kwargs):
        """
        In this method validate request query parameters and filter and return custom service list.
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
            # filter and get all service based on query params
            queryset = self.filter_queryset(self.params)
        except DjangoValidationError as err:
            error_msg, status_code = err.args[0], HTTP_400_BAD_REQUEST
        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err.args[0])
            error_msg, status_code = err.args[0], HTTP_500_INTERNAL_SERVER_ERROR

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

        return self.paginator.generate_response(queryset, CustomServiceListSerializer, request, is_pagination)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        In this method validate service from data and created new custom service.
        return success/error message.
        """
        request_data = request.data

        # create custom service serializers object
        serializer = self.serializer_class(data=request_data, context={'request': request})

        if not serializer.is_valid():
            return APIResponse(serializer.errors, HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # add new custom service
            instance = serializer.create(validated_data)
        except Exception as err:
            # roll back transaction if any exception occur while adding custom service
            transaction.savepoint_rollback(sid)
            logger.error("Unexpected error occurred :  %s.", err.args[0])
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        # convert model object into json
        data = CustomServiceViewSerializer(instance).data
        data['message'] = ADD_CUSTOM_SERVICE

        return APIResponse(data, HTTP_201_CREATED)


class CustomServiceRetrieveUpdateDeleteView(RetrieveUpdateDestroyAPIView):
    """
    An Api View which provides a method to get, update and delete custom service.
    Accepts the following GET/PUT/DELETE header parameters: access token
    Returns the success/fail message.
    """

    queryset = CustomService.objects.all()
    serializer_class = CustomServiceUpdateSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('change_customservice', 'view_customservice', 'delete_customservice',)
    lookup_field = ('vendor_id', 'pk',)

    def get_object(self):
        vendor_obj = None
        try:
            # get vendor object
            vendor_obj = Vendor.objects.get(id=self.kwargs['vendor_id'])
        except Exception as err:
            pass

        if vendor_obj is None:
            raise Http404(detail=INVALID_VENDOR_ID.format(self.kwargs['vendor_id']), attr_name="message")

        # get custom services
        custom_services = vendor_obj.services.filter(id=self.kwargs['pk'])

        if not custom_services:
            raise Http404(detail=INVALID_CUSTOM_SERVICE_ID.format(self.kwargs['vendor_id']), attr_name="message")

        return custom_services[0]

    def get(self, request, *args, **kwargs):
        # get vendor service object
        instance = self.get_object()

        # serialize custom service objects
        serializer = CustomServiceViewSerializer(instance)

        return APIResponse(serializer.data, HTTP_OK)

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        # get service object
        instance = self.get_object()

        # get request form data
        request_data = request.data

        # create custom service serializers object
        serializer = self.serializer_class(data=request_data, context={'request': request}, partial=True)

        if not serializer.is_valid():
            return APIResponse(serializer.errors, HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # update custom service
            instance = serializer.update(instance, validated_data)
        except Exception as err:
            logger.error("Unexpected error occurred 1 :  %s.", err.args[0])
            # roll back transaction if any exception occur while custom update service
            transaction.savepoint_rollback(sid)
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        # convert model object into json
        data = CustomServiceViewSerializer(instance).data
        data['message'] = UPDATE_CUSTOM_SERVICE

        return APIResponse(data, HTTP_OK)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        # validate and get service object
        instance = self.get_object()

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # soft delete custom service
            instance.delete()
        except Exception as err:
            # roll back transaction if any exception occur while delete custom service
            transaction.savepoint_rollback(sid)
            logger.error("Unexpected error occurred :  %s.", err.args[0])
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        return APIResponse({'message': DELETE_CUSTOM_SERVICE}, HTTP_OK)