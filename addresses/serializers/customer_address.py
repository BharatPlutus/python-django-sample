from django.utils import timezone
from rest_framework import serializers
from rest_framework.serializers import ValidationError

from common_config.api_message import INVALID_ZIP_CODE_NUMBER_LENGTH, EXTRA_FIELDS_IN_PAYLOAD, REQUIRED_FIELD
from utils.custom_validators.zip_code import validate_zip_code
from utils.serializers.address import AddressDefaultFieldMixin
from utils.custom_validators.phone_number import validate_phone_number as validate_phone_number_field

from addresses.models.customer_address import CustomerAddress
from addresses.serializers.common import CityViewSerializer, StateListSerializer, CountryViewSerializer
from stores.serializers.store import StoreSerializer
from customers.serializers.customer import CustomerViewSerializer


class ExcludeFields(object):
    @staticmethod
    def exclude_customer_fields(data):
        # exclude field from customer object
        include_fields = ("id", "user", "phone_number")
        nested_include_fields = ("id", "username", "email", "first_name", "last_name")

        # exclude customer user object fields
        data['customer']['user'] = {key: data for key, data in data['customer']['user'].items() if
                                    key in nested_include_fields}

        # exclude customer fields
        data['customer'] = {key: data for key, data in data['customer'].items() if key in include_fields}

        if "customer_id" in data:
            del data["customer_id"]
        return data


class CustomerAddressNestedViewSerializer(serializers.ModelSerializer):
    state = StateListSerializer(source='state_id')
    country = CountryViewSerializer(source='country_id')

    class Meta:
        model = CustomerAddress
        fields = ('id', 'first_name', 'last_name', 'is_billing_address', 'street1', 'street2', 'city', 'state',
                  'country', 'address_type', 'zip_code', 'is_default', "phone_number",)


class CustomerAddressViewSerializer(ExcludeFields, serializers.ModelSerializer):
    state = StateListSerializer(source='state_id')
    country = CountryViewSerializer(source='country_id')
    store = StoreSerializer(source='store_id')
    customer = CustomerViewSerializer(source='customer_id')

    class Meta:
        model = CustomerAddress
        fields = ('id', 'first_name', 'last_name', 'is_billing_address', 'street1', 'street2', 'city', 'state',
                  'country', 'store', 'customer', 'address_type', 'zip_code', 'is_default', 'is_active', 'created_by',
                  'updated_by', 'created_on', 'updated_on', "phone_number",)

    def __init__(self, *args, **kwargs):
        # get exclude field array
        self.exclude_fields = kwargs.pop('exclude_fields', None)
        super(CustomerAddressViewSerializer, self).__init__(*args, **kwargs)

    def to_representation(self, instance):
        data = super(CustomerAddressViewSerializer, self).to_representation(instance)

        if self.exclude_fields is not None and "customer" not in self.exclude_fields:
            # exclude extra fields
            data = self.exclude_customer_fields(data)

        if self.exclude_fields is not None:
            if "store" in self.exclude_fields and "store" in data:
                del data['store']

            if "customer" in self.exclude_fields and "customer" in data:
                del data['customer']

        return data


class CustomerAddressListSerializer(ExcludeFields, serializers.ModelSerializer):
    state = StateListSerializer(source='state_id')
    country = CountryViewSerializer(source='country_id')
    store = StoreSerializer(source='store_id')
    customer = CustomerViewSerializer(source='customer_id')

    class Meta:
        model = CustomerAddress
        fields = ('id', 'first_name', 'last_name', 'is_billing_address', 'street1', 'street2', 'city', 'state',
                  'country', 'store', 'customer', 'address_type', 'zip_code', 'is_default', 'is_active', 'created_by',
                  'updated_by', 'created_on', 'updated_on', "phone_number",)

    def __init__(self, *args, **kwargs):
        # get exclude field array
        self.exclude_fields = kwargs.pop('exclude_fields', None)
        super(CustomerAddressListSerializer, self).__init__(*args, **kwargs)

    def to_representation(self, instance):
        data = super(CustomerAddressListSerializer, self).to_representation(instance)

        if self.exclude_fields is not None and "customer" not in self.exclude_fields:
            # exclude extra fields
            data = self.exclude_customer_fields(data)

        if self.exclude_fields is not None:
            if "store" in self.exclude_fields and "store" in data:
                del data['store']

            if "customer" in self.exclude_fields and "customer" in data:
                del data['customer']

        return data


class CustomerAddressCreateUpdateSerializer(AddressDefaultFieldMixin, serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = "__all__"
        extra_kwargs = {
            "zip_code": {
                "error_messages": {
                    "max_length": INVALID_ZIP_CODE_NUMBER_LENGTH
                }
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__()

        # get exclude field array
        exclude_fields = kwargs.pop('exclude_fields', None)

        # get include field array
        include_fields = kwargs.pop('include_fields', None)

        self.custom_validate_fields = kwargs.pop('custom_validate_fields', [])

        super(CustomerAddressCreateUpdateSerializer, self).__init__(*args, **kwargs)

        if exclude_fields:
            for field_name in exclude_fields:
                # exclude field from fields
                self.fields.pop(field_name)

        if include_fields is not None:
            if "method" in include_fields:
                METHOD_CHOICE = (
                    ('POST', 'POST'),
                    ('PUT', 'PUT'),
                )
                # include fields
                self.fields["method"] = serializers.ChoiceField(required=True, choices=METHOD_CHOICE)
                self.fields["id"] = serializers.PrimaryKeyRelatedField(queryset=CustomerAddress.objects.all(),
                                                                       required=False)

    def validate_phone_number(self, value):
        # validate phone number
        validate_phone_number_field(value, 'phone_number')
        return value

    def validate(self, attrs):
        # validate zip code number
        if 'zip_code' in attrs:
            validate_zip_code(attrs['zip_code'])

        # check extra fields in payload, if found raise an error message
        if hasattr(self, 'initial_data'):
            extra_fields = set(self.initial_data.keys()) - set(self.fields.keys())
            if extra_fields:
                extra_fields = ", ".join(extra_fields)
                raise ValidationError({"message": EXTRA_FIELDS_IN_PAYLOAD.format(extra_fields)})

        if "method" in attrs:
            if attrs['method'] == "PUT" and "id" not in attrs:
                raise ValidationError({"id": REQUIRED_FIELD})

            if attrs['method'] == "POST":
                if "id" in attrs:
                    raise ValidationError({"message": EXTRA_FIELDS_IN_PAYLOAD.format("id")})

                if "phone_number" not in attrs:
                    raise ValidationError({"phone_number": REQUIRED_FIELD})

        if "phone_number" in self.custom_validate_fields:
            if "phone_number" not in attrs:
                raise ValidationError({"phone_number": REQUIRED_FIELD})

        if "validate_phone" in self.context:
            if "phone_number" not in attrs:
                raise ValidationError({"phone_number": REQUIRED_FIELD})

        return attrs

    def __setattr_user_object(self, attrs):
        user = self.context['request'].user
        attrs['created_by'] = user
        return attrs

    def create(self, validated_data):
        # set request user object
        validated_data = self.__setattr_user_object(validated_data)

        # filter address query
        filter_kwargs = {'customer_id': validated_data['customer_id'], 'is_default': True}

        # validate customer default address
        validated_data = self._check_default_address_exits(CustomerAddress, validated_data, filter_kwargs)

        # add new customer address
        instance = CustomerAddress.objects.create(**validated_data)
        return instance

    def update(self, instance, validated_data):
        # filter address query
        filter_kwargs = {'customer_id': instance.customer_id, 'is_default': True}

        # validate customer default address
        validated_data = self._check_default_address_exits(CustomerAddress, validated_data, filter_kwargs)

        # set request user object
        validated_data['updated_by'] = self.context['request'].user

        # update instance fields value
        for key, item in validated_data.items():
            setattr(instance, key, item)

        instance.updated_on = timezone.now()

        # update customer address details
        instance.save()
        return instance
