import ast
from django.db.models import Q
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView

from common_config.api_code import HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_OK, HTTP_500_INTERNAL_SERVER_ERROR
from common_config.api_message import ADD_SERVICE, UPDATE_SERVICE, INVALID_PAGE_SIZE, \
    DELETE_SERVICE, EXTRA_QUERY_PARAMS, INVALID_PAGE_NUMBER, INVALID_BOOLEAN_FLAG, BLANK_PARAM, INVALID_SORT_BY, \
    INVALID_SORT_BY_FIELD_PARAM, REQUIRED_PARAMS, INVALID_STATUS_FILTER, INVALID_SERVICE_IMAGE_ID
from common_config.constant import SERVICE_CATEGORY
from common_config.logger.logging_handler import logger
from common_config.generics import get_object_or_404
from utils.api_response import APIResponse
from utils.permissions import IsAuthorized
from utils.pagination import Pagination
from utils.views.service import ServiceListCreateMixin, ServiceRetrieveUpdateDeleteMixin

from services.models.service import Service
from services.serializers.service import ServiceCreateSerializer, ServiceViewSerializer, ServiceListSerializer, \
    ServiceUpdateSerializer
from price_groups.tasks.store_service import linked_services_to_store_task, linked_service_and_options_to_store_task


class ServiceListCreateView(ServiceListCreateMixin):
    """
    An Api View which provides a method to add new service or view list services.
    Accepts the following GET/POST header parameters: access token
    Returns the success/fail message.
    """
    queryset = Service.objects.all()
    serializer_class = ServiceCreateSerializer
    pagination_class = Pagination
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('add_service', 'list_service',)
    query_filter_params = ["is_active", "include_deleted", "page", "page_size", "status", "sort_by", "search",
                           "sort_by_field"]

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

        if "status" in self.params:
            try:
                self.params['status'] = ast.literal_eval(self.params['status'])
            except Exception as err:
                self.errors.setdefault("status", []).append(INVALID_STATUS_FILTER.format(
                    type(self.params['status']).__name__))

            if not isinstance(self.params['status'], list):
                self.errors.setdefault("status", []).append(INVALID_STATUS_FILTER.format(
                    type(self.params['status']).__name__))

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

        if "sort_by_field" in self.params and self.params['sort_by_field'] not in ["name", "description", "status",
                                                                                   "price"]:
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
                    IsAuthorized.has_include_deleted_permission(self.request, "list_service")

    def filter_queryset(self, params):
        filter_kwargs = {'is_active': True}
        if "is_active" in params and params['is_active'] in ['False']:
            filter_kwargs['is_active'] = False

        if "status" in params:
            filter_kwargs['status__in'] = params.get('status')

        if "sort_by_field" in params:
            if params['sort_by_field'] == "name":
                sort_by_field = "name"

            elif params['sort_by_field'] == "status":
                STATUS_CHOICE = Service.STATUS_CHOICES

                # sort service status
                service_status = sorted(STATUS_CHOICE, key=lambda tup: tup[1], reverse=True)

                # get sorted status
                sorted_list = [x[0] for x in service_status]

                from django.db.models import Case, When

                # sort by field
                sort_by_field = Case(
                    *[When(status=status, then=pos) for pos, status in enumerate(sorted_list)])

            elif params['sort_by_field'] == "description":
                sort_by_field = "description"

            else:
                sort_by_field = "price"
        else:
            sort_by_field = "created_on"

        query = Q()

        if "search" in params:
            query = Q(name__icontains=params['search']) | Q(description__icontains=params['search']) | \
                    Q(Q(category_tags__name__icontains=params['search']) &
                      Q(category_tags__entity_type=SERVICE_CATEGORY))

        for item in filter_kwargs:
            query = query & Q(**{item: filter_kwargs[item]})

        if "sort_by" in params and params['sort_by'] == "asc":
            return self.queryset.filter(query).order_by(sort_by_field)

        return self.queryset.filter(query).order_by(sort_by_field).reverse()

    def get(self, request, *args, **kwargs):
        """
        In this method validate request query parameters and filter and return service list.
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

        return self.paginator.generate_response(queryset, ServiceListSerializer, request, is_pagination)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        In this method validate service from data and created new service.
        return success/error message.
        """
        request_data = request.data.copy()

        try:
            # validate service and service option fields value
            serializer, validate_data = self.validate(request_data)
        except ValidationError as err:
            return APIResponse(err.args[0], HTTP_400_BAD_REQUEST)
        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # add new service
            instance, priceGroupServiceIdList = serializer.create(validate_data)
        except ValidationError as err:
            # roll back transaction if any exception occur while adding service and service option
            transaction.savepoint_rollback(sid)
            return APIResponse(err.args[0], HTTP_400_BAD_REQUEST)
        except Exception as err:
            # roll back transaction if any exception occur while adding service and service option
            transaction.savepoint_rollback(sid)
            logger.error("Unexpected error occurred :  %s.", err.args[0])
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        # convert model object into json
        data = ServiceViewSerializer(instance).data
        data['message'] = ADD_SERVICE

        if priceGroupServiceIdList:
            # system user assign services to store
            linked_services_to_store_task.delay({'priceGroupServiceIdList': priceGroupServiceIdList})

        return APIResponse(data, HTTP_201_CREATED)


class ServiceRetrieveUpdateDeleteView(ServiceRetrieveUpdateDeleteMixin):
    """
    An Api View which provides a method to get, update and delete service.
    Accepts the following GET/PUT/DELETE header parameters: access token
    Returns the success/fail message.
    """

    queryset = Service.objects.all()
    serializer_class = ServiceUpdateSerializer
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('change_service', 'view_service', 'delete_service',)
    lookup_field = 'pk'

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}

        # get object
        obj = get_object_or_404(queryset, "service_id", **filter_kwargs)
        return obj

    def get(self, request, *args, **kwargs):
        # get service object
        instance = self.get_object()

        # serialize service objects
        serializer = ServiceViewSerializer(instance)
        return APIResponse(serializer.data, HTTP_OK)

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        # get service object
        instance = self.get_object()

        # get request form data
        request_data = request.data

        try:
            # validate service and service option fields value
            serializer, validated_data = self.validate(request_data)
        except ValidationError as err:
            return APIResponse(err.args[0], HTTP_400_BAD_REQUEST)
        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        if "del_images" in validated_data and len(validated_data['del_images']) > 0:
            del_images = validated_data.get("del_images")
            errors = {}
            images = [x.id for x in instance.images.all()]

            for x in del_images:
                if x.id not in images:
                    errors.setdefault("del_images", []).append(INVALID_SERVICE_IMAGE_ID.format(x.id))

            if len(errors) > 0:
                return APIResponse(errors, HTTP_400_BAD_REQUEST)

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # update service
            instance, priceGroupServiceIdList = serializer.update(instance, validated_data)
        except ValidationError as err:
            logger.error("validation error occurred 1 :  %s.", err.args[0])
            # roll back transaction if any exception occur while adding service and service option
            transaction.savepoint_rollback(sid)
            return APIResponse(err.args[0], HTTP_400_BAD_REQUEST)
        except Exception as err:
            logger.error("Unexpected error occurred 2 :  %s.", err.args[0])
            # roll back transaction if any exception occur while update service and service option
            transaction.savepoint_rollback(sid)
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        # convert model object into json
        data = ServiceViewSerializer(instance).data
        data['message'] = UPDATE_SERVICE

        task_payload = {}
        if priceGroupServiceIdList:
            task_payload['priceGroupServiceIdList'] = priceGroupServiceIdList

        if "createOptionIds" in request.session:
            task_payload['createOptionIds'] = request.session['createOptionIds']
            del request.session['createOptionIds']

        if task_payload:
            # system user assign services to store
            linked_service_and_options_to_store_task.delay(task_payload)

        return APIResponse(data, HTTP_OK)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        # validate and get service object
        instance = self.get_object()

        # get last transaction save point id
        sid = transaction.savepoint()

        try:
            # soft delete service
            instance.delete()
        except Exception as err:
            # roll back transaction if any exception occur while delete service
            transaction.savepoint_rollback(sid)
            logger.error("Unexpected error occurred :  %s.", err.args[0])
            return APIResponse({"message": err.args[0]}, HTTP_400_BAD_REQUEST)

        return APIResponse({'message': DELETE_SERVICE}, HTTP_OK)


class UpdateServiceOptionSequenceNumber(ListAPIView):
    """
    An Api View which provides a method to update service option sequence number.
    Accepts the following GET header parameters: access token
    Returns the success/fail message.
    """

    queryset = Service.objects.all()
    permission_classes = (IsAuthenticated, IsAuthorized,)
    permission_required = ('change_service',)

    def get(self, request, *args, **kwargs):
        services = Service.objects.all()

        for service_obj in services:

            options = service_obj.options.all().order_by("id")
            sequence = 1

            for option_obj in options:
                option_obj.sequence = sequence
                option_obj.save()

                # update price group service option
                for price_list_option_obj in option_obj.price_group_options.all():
                    price_list_option_obj.sequence = sequence
                    price_list_option_obj.save()

                sequence += 1

        return APIResponse({'message': "Service option sequence updated successfully."}, HTTP_OK)