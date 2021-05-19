from django.utils import timezone
from rest_framework import serializers
from rest_framework.serializers import ValidationError

from common_config.api_message import INVALID_ZIP_CODE_NUMBER_LENGTH, EXTRA_FIELDS_IN_PAYLOAD, REQUIRED_FIELD
from utils.custom_validators.zip_code import validate_zip_code
from utils.serializers.address import AddressDefaultFieldMixin
from utils.custom_validators.phone_number import validate_phone_number as validate_phone_number_field
from addresses.models.vendor_address import VendorAddress
from addresses.serializers.common import StateListSerializer, CountryViewSerializer
from vendors.serializers.vendor import VendorADDViewSerializer


class VendorAddressNestedViewSerializer(serializers.ModelSerializer):
    state = StateListSerializer(source='state_id')
    country = CountryViewSerializer(source='country_id')

    class Meta:
        model = VendorAddress
        fields = "__all__"


class VendorAddressViewSerializer(serializers.ModelSerializer):
    state = StateListSerializer(source='state_id')
    country = CountryViewSerializer(source='country_id')
    vendor = VendorADDViewSerializer(source='vendor_id')

    class Meta:
        model = VendorAddress
        fields = ('id', 'street1', 'street2', 'city', 'state', 'country', 'label', 'zip_code', 'is_default',
                  'is_active', 'vendor', 'created_by', 'updated_by', 'created_on', 'updated_on', "phone_number", )


class VendorAddressListSerializer(serializers.ModelSerializer):
    state = StateListSerializer(source='state_id')
    country = CountryViewSerializer(source='country_id')
    vendor = VendorADDViewSerializer(source='vendor_id')

    class Meta:
        model = VendorAddress
        fields = ('id', 'street1', 'street2', 'city', 'state', 'country', 'label', 'zip_code', 'is_default',
                  'is_active', 'vendor', 'created_by', 'updated_by', 'created_on', 'updated_on', "phone_number", )


class VendorAddressCreateUpdateSerializer(AddressDefaultFieldMixin, serializers.ModelSerializer):
    class Meta:
        model = VendorAddress
        fields = "__all__"
        extra_kwargs = {
            "zip_code": {
                "error_messages": {
                    "max_length": INVALID_ZIP_CODE_NUMBER_LENGTH
                }
            }
        }

    def validate_zip_code(self, value):
        # validate zip code number
        validate_zip_code(value)
        return value

    def validate_phone_number(self, value):
        # validate phone number
        validate_phone_number_field(value, 'phone_number')
        return value

    def validate(self, attrs):
        errors = {}

        # check extra fields in payload, if found raise an error message
        if hasattr(self, 'initial_data'):
            extra_fields = set(self.initial_data.keys()) - set(self.fields.keys())
            if extra_fields:
                extra_fields = ", ".join(extra_fields)
                errors.setdefault("message", []).append(EXTRA_FIELDS_IN_PAYLOAD.format(extra_fields))

        if self.context['request'].method == "POST":
            if "vendor_id" not in attrs:
                errors.setdefault("vendor_id", []).append(REQUIRED_FIELD)

            if "phone_number" not in attrs:
                errors.setdefault("phone_number", []).append(REQUIRED_FIELD)

        if errors:
            raise ValidationError(errors)

        return attrs

    def __setattr_user_object(self, attrs):
        user = self.context['request'].user
        attrs['created_by'] = user
        return attrs

    def create(self, validated_data):
        # set request user object
        validated_data = self.__setattr_user_object(validated_data)

        # filter address query
        filter_kwargs = {'vendor_id': validated_data['vendor_id'].id, 'is_default': True}

        # validate vendor default address
        validated_data = self._check_default_address_exits(VendorAddress, validated_data, filter_kwargs)

        # add new address
        instance = VendorAddress.objects.create(**validated_data)
        return instance

    def update(self, instance, validated_data):
        validated_data['updated_by'] = self.context['request'].user

        # filter address query
        filter_kwargs = {'vendor_id': instance.vendor_id.id, 'is_default': True}

        # validate vendor default address
        validated_data = self._check_default_address_exits(VendorAddress, validated_data, filter_kwargs)

        # setter to set instance value
        for key, item in validated_data.items():
            setattr(instance, key, item)

        instance.updated_on = timezone.now()

        # saved updated vendor address value
        instance.save()

        return instance
