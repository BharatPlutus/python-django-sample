from django.db.models import Q
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.permissions import AllowAny
from rest_framework.generics import ListAPIView, RetrieveAPIView

from common_config.api_code import HTTP_400_BAD_REQUEST, HTTP_OK
from common_config.api_message import INVALID_PAGE_SIZE, INVALID_PAGE_NUMBER, \
    INVALID_REQUEST_QUERY_PARAMETERS, INVALID_MAX_PRICE_TYPE, \
    INVALID_MIN_PRICE_TYPE, INVALID_MOST_POPULAR_FLAG, INVALID_IS_CUSTOMER_SIDE_FLAG, INVALID_SERVICE_SEARCH_FIELD, \
    INVALID_MIN_PRICE_MUST_LESS_THAN_MAX, \
    INVALID_SEARCH_SERVICE_ITEM_CATEGORIES, INVALID_SEARCH_SERVICE_ITEM_CATEGORIES_TAG, \
    INVALID_SEARCH_SERVICE_TOP_LEVEL, INVALID_SEARCH_SERVICE_TOP_LEVEL_TAG, INVALID_IS_PARTIAL_FLAG, \
    INVALID_SERVICE_SEARCH_BY_NAME, INCOMPLETE_ON_BOARDING_PROCESS, STORE_DOES_NOT_ASSIGN_PRICE_LIST
from common_config.constant import SERVICE_CATEGORY, ITEM_CATEGORY
from common_config.generics import get_object_or_404
from common_config.logger.logging_handler import logger
from utils.api_response import APIResponse
from utils.pagination import Pagination

from stores.models.store import Store
from services.models.popular_service import PopularService
from price_groups.models.price_group_service import PriceGroupService, StorePriceGroupService
from price_groups.serializers.price_group_service import CustomerPortalServiceViewSerializer, \
    CustomerPortalServicePartialDataListSerializer


class CustomerPortalServiceView(ListAPIView):
    """
    An Api View which provides a method to filter services.
    Accepts the following GET header parameters: access token
    Returns the success/fail message.
    """

    queryset = PriceGroupService.objects.all()
    serializer_class = CustomerPortalServiceViewSerializer
    permission_classes = (AllowAny,)
    pagination_class = Pagination
    lookup_field = 'pk'
    query_filter_params = ["page", "page_size", "name", "max_price", "min_price", "most_popular", "item_tags",
                           "top_level_tags", "store_id", "is_customer_side", "is_partial", "search"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.errors = {}
        self.params = dict()
        self.top_level_tags = None
        self.item_tags = None
        self.popular_services = []
        self.is_partial = False

    def get_object(self):
        queryset = Store.objects.all()

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}

        # get object
        obj = get_object_or_404(queryset, "store_id", **filter_kwargs)

        return obj

    def validate_query_param(self, page_size, page):
        # check pre define query parameter if contain extra query param then raise error message
        if len(self.params) > 0 and not all(key in self.query_filter_params for key in self.params.keys()):
            extra_param = [key for key in self.params if key not in self.query_filter_params]
            self.errors.setdefault("message", []).append(INVALID_REQUEST_QUERY_PARAMETERS.format(extra_param))

        # check page size must  number
        if "page_size" in self.params and not page_size.isnumeric():
            self.errors.setdefault("page_size", []).append(INVALID_PAGE_SIZE)

        if "page" in self.params and not page.isnumeric():
            self.errors.setdefault("page", []).append(INVALID_PAGE_NUMBER)

        if "max_price" in self.params and not self.params['max_price'].isnumeric():
            self.errors.setdefault("max_price", []).append(INVALID_MAX_PRICE_TYPE.format(
                type(self.params['max_price']).__name__))

        if "min_price" in self.params and not self.params['min_price'].isnumeric():
            self.errors.setdefault("min_price", []).append(INVALID_MIN_PRICE_TYPE.format(
                type(self.params['min_price']).__name__))

        if "most_popular" in self.params and self.params['most_popular'] not in ['true', 'false']:
            self.errors.setdefault("most_popular", []).append(INVALID_MOST_POPULAR_FLAG)

        if "is_partial" in self.params and self.params['is_partial'] not in ['true', 'false']:
            self.errors.setdefault("is_partial", []).append(INVALID_IS_PARTIAL_FLAG)
        else:
            if "is_partial" in self.params and self.params['is_partial'] == 'true':
                self.is_partial = True

        if "is_customer_side" in self.params and self.params['is_customer_side'] not in ['true']:
            self.errors.setdefault("is_customer_side", []).append(INVALID_IS_CUSTOMER_SIDE_FLAG)

        if "name" in self.params and self.params['name'] == "":
            self.errors.setdefault("name", []).append(INVALID_SERVICE_SEARCH_BY_NAME)

        if "search" in self.params and self.params['search'] == "":
            self.errors.setdefault("search", []).append(INVALID_SERVICE_SEARCH_FIELD)

        if "min_price" in self.params and self.params['min_price'].isnumeric() and "max_price" in self.params \
                and self.params['max_price'].isnumeric():
            if self.params['min_price'] > self.params['max_price']:
                self.errors.setdefault("min_price", []).append(INVALID_MIN_PRICE_MUST_LESS_THAN_MAX)

        item_tags = self.request.GET.get('item_tags', None)

        if "item_tags" in self.params and item_tags == "":
            self.errors.setdefault("item_tags", []).append(INVALID_SEARCH_SERVICE_ITEM_CATEGORIES)
        elif item_tags is not None:
            try:
                self.item_tags = [x.strip() for x in item_tags.split(",")]
            except Exception as err:
                logger.error("Unexpected error occurred :  %s.", err)
                self.errors.setdefault("item_tags", []).append(INVALID_SEARCH_SERVICE_ITEM_CATEGORIES)
            else:
                if not isinstance(self.item_tags, list):
                    self.errors.setdefault("item_tags", []).append(INVALID_SEARCH_SERVICE_ITEM_CATEGORIES)
                else:
                    item_tags_error = []
                    # validate item tag id
                    for idx, item_tag in enumerate(self.item_tags):
                        if not item_tag.isnumeric():
                            item_tags_error.append(INVALID_SEARCH_SERVICE_ITEM_CATEGORIES_TAG.format(
                                type(item_tag).__name__))
                    if item_tags_error:
                        self.errors.setdefault("item_tags", []).extend(item_tags_error)

        top_level_tags = self.request.GET.get('top_level_tags', None)

        if "top_level_tags" in self.params and top_level_tags == "":
            self.errors.setdefault("top_level_tags", []).append(INVALID_SEARCH_SERVICE_TOP_LEVEL)
        elif top_level_tags is not None:
            try:
                self.top_level_tags = [x.strip() for x in top_level_tags.split(",")]
            except Exception as err:
                logger.error("Unexpected error occurred :  %s.", err)
                self.errors.setdefault("top_level_tags", []).append(INVALID_SEARCH_SERVICE_TOP_LEVEL)
            else:
                if not isinstance(self.top_level_tags, list):
                    self.errors.setdefault("top_level_tags", []).append(INVALID_SEARCH_SERVICE_TOP_LEVEL)
                else:
                    top_level_tags_error = []
                    # validate top level tag id
                    for idx, top_level_tag in enumerate(self.top_level_tags):
                        if not top_level_tag.isnumeric():
                            top_level_tags_error.append(INVALID_SEARCH_SERVICE_TOP_LEVEL_TAG.format(
                                type(top_level_tag).__name__))

                    if top_level_tags_error:
                        self.errors.setdefault("top_level_tags", []).extend(top_level_tags_error)

    @staticmethod
    def get_all_store_service(store_obj):
        price_group_obj = store_obj.price_group.price_group_id

        service_list = [x.id for x in price_group_obj.services.filter(service_id__is_active=True,
                                                                      service_id__status=2).order_by("id")]

        store_price_group_list = StorePriceGroupService.objects.filter(price_group_service_id__in=service_list,
                                                                       store_id=store_obj.id,
                                                                       is_active=True,
                                                                       is_enabled=True).order_by("id")
        store_service_list = []

        for xx in store_price_group_list:
            if xx.price_group_service_id.id not in store_service_list:
                store_service_list.append(xx.price_group_service_id.id)

        return store_service_list

    @staticmethod
    def most_popular_services(store_id, count):
        try:
            return PopularService.objects.filter(store_id=store_id, count__gte=count).order_by("count").reverse()
        except Exception as err:
            logger.error("Un-excepted error %s", err.args[0])
        return []

    def service_filter_queryset(self, params, store_obj):
        filter_kwargs = dict(service_id__status=2, is_enabled=True)
        filter_kwargs['id__in'] = self.get_all_store_service(store_obj)

        if "max_price" in params and "min_price" in params:
            filter_kwargs['price__range'] = (params['min_price'], params['max_price'])

        if "max_price" in params and "min_price" not in params:
            filter_kwargs['price__range'] = (0, params['max_price'])

        if "min_price" in params and "max_price" not in params:
            filter_kwargs['price__gte'] = params['min_price']

        if self.item_tags is not None and len(self.item_tags) > 0:
            filter_kwargs['service_id__item_tags__in'] = self.item_tags

        if self.top_level_tags is not None and len(self.top_level_tags) > 0:
            filter_kwargs['service_id__category_tags__in'] = self.top_level_tags

        self.popular_services = self.most_popular_services(store_obj.id, store_obj.settings.popular_service_count)

        if "most_popular" in params and params['most_popular'] == "true":
            filter_kwargs['service_id__in'] = [ss.service_id for ss in self.popular_services]
            return self.queryset.filter(**filter_kwargs)

        if "name" in params:
            query = Q(service_id__name__icontains=params['name'])
            for item in filter_kwargs:
                query = query & Q(**{item: filter_kwargs[item]})

            return self.queryset.filter(query)

        if "search" in params:
            query = Q(service_id__name__icontains=params['search']) | \
                    Q(Q(service_id__category_tags__name__icontains=params['search']) &
                      Q(service_id__category_tags__entity_type=SERVICE_CATEGORY)) | \
                    Q(Q(service_id__item_tags__name__icontains=params['search']) &
                      Q(service_id__item_tags__entity_type=ITEM_CATEGORY))

            for item in filter_kwargs:
                query = query & Q(**{item: filter_kwargs[item]})

            return self.queryset.filter(query)

        return self.queryset.filter(**filter_kwargs)

    def get(self, request, *args, **kwargs):
        """
        In this method validate request query parameters and filter and return service list.
        return success/error message.
        """
        # validate and get store object
        store_obj = self.get_object()

        if not store_obj.is_onboarding_complete:
            return APIResponse({"error": INCOMPLETE_ON_BOARDING_PROCESS}, HTTP_400_BAD_REQUEST)

        try:
            store_obj.price_group
        except Exception as err:
            return APIResponse({"error": STORE_DOES_NOT_ASSIGN_PRICE_LIST}, HTTP_400_BAD_REQUEST)

        self.params = request.query_params
        page_size = self.params.get('page_size', None)
        page = self.params.get('page', None)

        # validate filter service params
        self.validate_query_param(page_size, page)

        if len(self.errors) > 0:
            return APIResponse({"error": self.errors}, HTTP_400_BAD_REQUEST)

        error_msg = None

        try:
            # filter and get all service based on query params
            queryset = self.service_filter_queryset(self.params, store_obj)
        except DjangoValidationError as err:
            error_msg = err.args[0]
        except Exception as err:
            logger.error("Unexpected error occurred :  %s.", err)
            error_msg = err.args[0]

        if error_msg is not None:
            return APIResponse({"error": error_msg}, HTTP_400_BAD_REQUEST)

        if self.is_partial:
            data = CustomerPortalServicePartialDataListSerializer(queryset, many=True,
                                                                  context={
                                                                      'popular_services': self.popular_services,
                                                                      'is_customer_side': True,
                                                                      'store_id': store_obj}).data
        else:
            data = CustomerPortalServiceViewSerializer(queryset, many=True,
                                                       context={
                                                           'popular_services': self.popular_services,
                                                           'is_customer_side': True,
                                                           'store_id': store_obj}).data

        if "is_customer_side" in self.params:
            categories_dict = {}
            item_tags_dict = {}
            service_group_dict = {}

            if store_obj.insurance_id is not None:
                insurance_obj = store_obj.insurance_id
                insurance = dict(name=insurance_obj.name, description=insurance_obj.description,
                                 option_type=insurance_obj.option_type, price=insurance_obj.price)
            else:
                insurance = dict()

            for iii in data:
                if "items" in iii['service'] and len(iii['service']['items']) > 0:
                    for x in iii['service']['items']:
                        if x['id'] not in item_tags_dict:
                            item_tags_dict.setdefault(x['id'], x)

                if "categories" in iii['service'] and len(iii['service']['categories']) > 0:
                    for x in iii['service']['categories']:
                        if x['id'] not in categories_dict:
                            categories_dict.setdefault(x['id'], x)
                        service_group_dict.setdefault(x['name'].strip(), []).append(iii)

            # sort item and categories
            categories = {s[0]: s[1] for s in sorted(categories_dict.items(), key=lambda k_v: k_v[1]['sequence'])}
            item_tags = {s[0]: s[1] for s in sorted(item_tags_dict.items(), key=lambda k_v: k_v[1]['sequence'])}

            # sort service group
            categories_name = [y['name'].strip() for x, y in categories.items()]
            service_group = {key: service_group_dict[key] for key in categories_name if key in service_group_dict}

            result = dict(services=service_group, item_tags=item_tags, categories=categories, insurance=insurance)

            return APIResponse(result, HTTP_OK)

        return APIResponse(data, HTTP_OK)


class CustomerPortalServiceDetailView(RetrieveAPIView):
    """
      An Api View which provides a method to filter services.
      Accepts the following GET header parameters: access token
      Returns the success/fail message.
      """

    queryset = PriceGroupService.objects.all()
    serializer_class = CustomerPortalServiceViewSerializer
    permission_classes = (AllowAny,)
    lookup_field = ("store_id", "pk")

    def get_object(self):
        queryset = StorePriceGroupService.objects.all()

        # Perform the lookup filtering.
        filter_kwargs = {'price_group_service_id': self.kwargs['pk'], 'store_id': self.kwargs['store_id'],
                         'is_active': True, 'is_enabled': True}

        # get object
        obj = get_object_or_404(queryset, "service_id", **filter_kwargs)

        return obj

    def get(self, request, *args, **kwargs):
        """
        In this method validate request query parameters and filter and return service list.
        return success/error message.
        """
        # validate and get store service object
        service_obj = self.get_object()

        if not service_obj.store_id.is_onboarding_complete:
            return APIResponse({"error": INCOMPLETE_ON_BOARDING_PROCESS}, HTTP_400_BAD_REQUEST)

        try:
            data = CustomerPortalServiceViewSerializer(service_obj.price_group_service_id,
                                                       context={
                                                           'popular_services': [],
                                                           'is_customer_side': True,
                                                           'store_id': service_obj.store_id}).data
        except Exception as err:
            return APIResponse({"error": err.args[0]}, HTTP_400_BAD_REQUEST)

        return APIResponse(data, HTTP_OK)
