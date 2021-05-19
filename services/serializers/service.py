from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from common_config.api_message import EXTRA_FIELDS_IN_PAYLOAD, ZERO_DECIMAL_VALUE, NOT_FOUND_JSON_DATA, \
    REQUIRED_FIELD, INVALID_ADDRESS_ID
from common_config.models.category import Category
from common_config.models.image import Image
from common_config.serializers.category import CategorySerializer
from common_config.constant import SERVICE_CATEGORY, ITEM_CATEGORY
from common_config.serializers.image import ImageSerializer

from addresses.serializers.store_address import StoreAddressListSerializer
from price_groups.models.price_group import PriceGroup
from price_groups.utils.price_list_service import add_or_update_price_list_services
from services.models.service import Service
from services.serializers.service_option import ServiceOptionListSerializer
from services.serializers.service_image import ServiceImageAddSerializer


class ServiceImageSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True)

    class Meta:
        model = Service
        fields = ("images",)
        read_only_fields = fields


class ServiceFilterListSerializer(serializers.ModelSerializer):
    category_tags = CategorySerializer(Category.objects.filter(entity_type=SERVICE_CATEGORY), many=True)
    item_tags = CategorySerializer(Category.objects.filter(entity_type=ITEM_CATEGORY), many=True)
    options = serializers.SerializerMethodField('get_options')

    class Meta:
        model = Service
        fields = '__all__'

    def get_options(self, service):
        # get service option instance
        options = service.options.filter(is_active=True).order_by("sequence")

        # get service option serializer data
        serializer = ServiceOptionListSerializer(options, many=True)
        return serializer.data

    def to_representation(self, instance):
        data = super(ServiceFilterListSerializer, self).to_representation(instance)
        if "address_id" in data:
            del data['address_id']

        return data


class ServiceListSerializer(serializers.ModelSerializer):
    category_tags = CategorySerializer(Category.objects.filter(entity_type=SERVICE_CATEGORY), many=True)
    item_tags = CategorySerializer(Category.objects.filter(entity_type=ITEM_CATEGORY), many=True)
    images = ImageSerializer(many=True)

    class Meta:
        model = Service
        fields = "__all__"

    def to_representation(self, instance):
        data = super(ServiceListSerializer, self).to_representation(instance)
        return data


class ServiceViewSerializer(serializers.ModelSerializer):
    address = StoreAddressListSerializer(source='address_id')
    category_tags = CategorySerializer(Category.objects.filter(entity_type=SERVICE_CATEGORY), many=True)
    item_tags = CategorySerializer(Category.objects.filter(entity_type=ITEM_CATEGORY), many=True)
    price_list = serializers.SerializerMethodField('get_price_list')
    options = serializers.SerializerMethodField('get_options')
    images = ImageSerializer(many=True)

    class Meta:
        model = Service
        fields = ("id", "name", "price", "description", "is_default", "is_active", "status", "options", "address",
                  "category_tags", "item_tags", "price_list", "created_on", "updated_on", "created_by", "updated_by",
                  "images",)

    def get_price_list(self, service):
        # get price group
        price_groups = PriceGroup.objects.filter(services__service_id=service.id, services__is_active=True)

        data = []

        for price_group in price_groups:
            price_group_json = dict(id=price_group.id, name=price_group.name)
            data.append(price_group_json)

        return data

    def get_options(self, service):
        # get service option instance
        options = service.options.filter(is_active=True).order_by("sequence")

        # get service option serializer data
        serializer = ServiceOptionListSerializer(options, many=True)

        return serializer.data

    def to_representation(self, instance):
        data = super(ServiceViewSerializer, self).to_representation(instance)

        if "address" in data:
            if data['address'] is not None and "store" in data['address']:
                del data['address']['store']
        return data


class PriceGroupServiceFilterListSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField('get_options')
    images = ImageSerializer(many=True)

    class Meta:
        model = Service
        fields = ("id", "name", "price", "description", "is_default", "is_active", "status",
                  "options", "created_on", "updated_on", "created_by", "updated_by", "images", )

    def get_options(self, service):
        # get service option instance
        options = service.options.filter(is_active=True).order_by("sequence")

        # get service option serializer data
        serializer = ServiceOptionListSerializer(options, many=True)

        return serializer.data


class ServiceMixinSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category_tags = None
        self.item_tags = None
        self.price_list = None
        self.createServiceOptions = None
        self.updateServiceOptions = None

    def validate_price(self, value):
        if value == 0:
            raise ValidationError(ZERO_DECIMAL_VALUE.format("price"))
        return value

    def _add_tags(self, service_instance):
        """ Add/Update service category and item tags"""

        if self.category_tags is not None:

            # un-reference all old data
            service_instance.category_tags.clear()

            if len(self.category_tags) > 0:
                category_tags = Category.get_or_create_categories(self.category_tags, SERVICE_CATEGORY)

                # add service category tags
                service_instance.category_tags.add(*category_tags)

        if self.item_tags is not None:

            # un-reference all old data
            service_instance.item_tags.clear()

            if len(self.item_tags) > 0:
                item_tags = Category.get_or_create_categories(self.item_tags, ITEM_CATEGORY)

                # add service item tags
                service_instance.item_tags.add(*item_tags)

    def common(self, data):
        if "item_tags" in data:
            self.item_tags = data.pop("item_tags")

        if "category_tags" in data:
            self.category_tags = data.pop("category_tags")

        if "price_list" in data:
            self.price_list = data.pop("price_list")

        return data

    @staticmethod
    def set_service_option_object(action_by, user, instance, service_options_data):
        for option in service_options_data:
            option['service_id'] = instance
            option[action_by] = user
        return service_options_data

    def create_or_update_service_option(self, instance, user):
        option_sequence_mapping = {}
        option_logic_rules = []
        service_option_obj = None

        if self.createServiceOptions is not None:
            add_service_options_data = self.createServiceOptions.get("validated_data")
            service_option_obj = self.createServiceOptions.get("serializer")

            # create service option
            option_logic_rules, option_sequence_mapping = service_option_obj.create(self.set_service_option_object(
                "created_by", user, instance, add_service_options_data))

        if self.updateServiceOptions is not None:
            update_service_options_data = self.updateServiceOptions.get("validated_data")
            service_option_obj = self.updateServiceOptions.get("serializer")

            # update service option
            option_logic, option_sequence = service_option_obj.update_bulk_records(self.set_service_option_object(
                "updated_by", user, instance, update_service_options_data))

            if len(option_logic_rules) > 0:
                option_logic_rules.extend(option_logic)
            else:
                option_logic_rules = option_logic

            if len(option_sequence_mapping) > 0:
                option_sequence_mapping.update(option_sequence)
            else:
                option_sequence_mapping = option_sequence

        # create/update service option logic
        if len(option_logic_rules) > 0 and len(option_sequence_mapping) > 0 and service_option_obj is not None:
            service_option_obj.create_service_option_logic(option_sequence_mapping, option_logic_rules)

    @staticmethod
    def create_service_images(images, instance):
        """
         Upload service images
        :param images:
        :param instance:
        :return:
        """
        image_ids = []

        for xx in images:
            xx['image_type'] = 'service_image'

        # upload service image
        img_instances = Image.upload_new_images(*images)
        image_ids.extend(img_instances)

        # map with service
        instance.images.add(*image_ids)


class ServiceCreateSerializer(ServiceMixinSerializer):
    category_tags = serializers.ListField(child=serializers.CharField(max_length=1000), write_only=True, required=True)
    item_tags = serializers.ListField(child=serializers.CharField(max_length=1000), write_only=True, required=False)
    price_list = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=PriceGroup.objects.all()),
                                       required=False, allow_null=False, allow_empty=False)
    images = ServiceImageAddSerializer(many=True, required=True, allow_null=False)

    class Meta:
        model = Service
        fields = ("name", "description", "price", "category_tags", "item_tags", "address_id", "status", "is_default",
                  "price_list", "images", "is_active",)

    def validate(self, attrs):
        errors = {}

        # check extra fields in payload, if found raise an error message
        if hasattr(self, 'initial_data'):
            extra_fields = set(self.initial_data.keys()) - set(self.fields.keys())
            if extra_fields:
                extra_fields = ", ".join(extra_fields)
                errors.setdefault("message", []).append(EXTRA_FIELDS_IN_PAYLOAD.format(extra_fields))

        if "images" in attrs and len(attrs['images']) <= 0:
            errors.setdefault("images", []).append(NOT_FOUND_JSON_DATA)

        if "address_id" not in attrs:
            errors.setdefault("address_id", []).append(REQUIRED_FIELD)

        if errors:
            raise ValidationError(errors)

        return attrs

    def create(self, validated_data):
        if "createServiceOptions" in validated_data:
            self.createServiceOptions = validated_data.pop("createServiceOptions")

        # # get current login user object from context and set in create_by and updated_by
        user = self.context['request'].user
        validated_data['created_by'] = user
        images = validated_data.pop("images", None)
        priceGroupServiceIdList = []

        # clean from data format
        clean_data = self.common(validated_data)

        # create new service
        instance = Service.objects.create(**clean_data)

        # add service category and item tags
        self._add_tags(instance)

        # create or update service option
        self.create_or_update_service_option(instance, user)

        if images is not None:
            self.create_service_images(images, instance)

        if self.price_list is not None:
            # add price list
            priceGroupServiceIdList = add_or_update_price_list_services(self.price_list, instance, user, True)

        return instance, priceGroupServiceIdList


class ServiceUpdateSerializer(ServiceMixinSerializer):
    category_tags = serializers.ListField(child=serializers.CharField(max_length=1000), write_only=True, required=True,
                                          allow_empty=True)
    item_tags = serializers.ListField(child=serializers.CharField(max_length=1000), write_only=True, required=False,
                                      allow_empty=True)
    price_list = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=PriceGroup.objects.all()),
                                       required=False, allow_empty=True)
    del_images = serializers.ListField(required=False, child=serializers.PrimaryKeyRelatedField(
        queryset=Image.objects.all()), allow_null=False, allow_empty=False)
    images = ServiceImageAddSerializer(many=True, required=False, allow_null=False)

    class Meta:
        model = Service
        fields = ("name", "description", "price", "category_tags", "item_tags", "address_id", "status", "is_default",
                  "price_list", "images", "del_images",)
        extra_kwargs = {
            'created_by': {'read_only': True}
        }

    def validate(self, attrs):
        errors = {}

        # check extra fields in payload, if found raise an error message
        if hasattr(self, 'initial_data'):
            extra_fields = set(self.initial_data.keys()) - set(self.fields.keys())
            if extra_fields:
                extra_fields = ", ".join(extra_fields)
                errors.setdefault("message", []).append(EXTRA_FIELDS_IN_PAYLOAD.format(extra_fields))

        if "images" in attrs and len(attrs['images']) <= 0:
            errors.setdefault("images", []).append(NOT_FOUND_JSON_DATA)

        if "address_id" in attrs and attrs['address_id'] is None:
            errors.setdefault("address_id", []).append(INVALID_ADDRESS_ID.format(attrs['address_id']))

        if errors:
            raise ValidationError(errors)

        return attrs

    def update(self, instance, validated_data):
        if "createServiceOptions" in validated_data:
            self.createServiceOptions = validated_data.pop("createServiceOptions")

        if "updateServiceOptions" in validated_data:
            self.updateServiceOptions = validated_data.pop("updateServiceOptions")

        # set current login user object
        user = self.context['request'].user
        validated_data['updated_by'] = user
        del_images = validated_data.pop("del_images", None)
        images = validated_data.pop("images", None)
        priceGroupServiceIdList = []

        # clean validated_data format
        clean_data = self.common(validated_data)

        if clean_data:
            # update service
            for key, item in clean_data.items():
                setattr(instance, key, item)

            instance.updated_on = timezone.now()

            # update instance
            instance.save()

        # add/update service category and item tags
        self._add_tags(instance)

        # create or update service option
        self.create_or_update_service_option(instance, user)

        if del_images is not None:
            Image.delete_bulk_images(del_images)

        if images is not None:
            self.create_service_images(images, instance)

        if self.price_list is not None:
            # update price list
            priceGroupServiceIdList = add_or_update_price_list_services(self.price_list, instance, user)

        return instance, priceGroupServiceIdList
