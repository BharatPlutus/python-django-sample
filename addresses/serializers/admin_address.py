from django.utils import timezone
from rest_framework import serializers
from rest_framework.serializers import ValidationError

from common_config.api_message import INVALID_ZIP_CODE_NUMBER_LENGTH, INVALID_NUMBER_LENGTH, EXTRA_FIELDS_IN_PAYLOAD
from utils.custom_validators.zip_code import validate_zip_code
from utils.custom_validators.phone_number import validate_phone_number
from utils.serializers.address import AddressDefaultFieldMixin

from addresses.models.admin_address import AdminAddress
from addresses.serializers.common import StateListSerializer, CountryViewSerializer


class AddressListSerializer(serializers.ModelSerializer):
    state = StateListSerializer(source='state_id')
    country = CountryViewSerializer(source='country_id')

    class Meta:
        model = AdminAddress
        fields = (
            'id', 'street1', 'street2', 'city', 'state', 'country', 'label', 'number',
            'zip_code', 'is_default', 'is_active', 'created_by', 'updated_by', 'created_on', 'updated_on')


class AddressViewSerializer(serializers.ModelSerializer):
    state = StateListSerializer(source='state_id')
    country = CountryViewSerializer(source='country_id')

    class Meta:
        model = AdminAddress
        fields = (
            'id', 'street1', 'street2', 'city', 'state', 'country', 'label', 'number',
            'zip_code', 'is_default', 'is_active', 'created_by', 'updated_by', 'created_on', 'updated_on')


class AddressCreateUpdateSerializer(AddressDefaultFieldMixin, serializers.ModelSerializer):
    class Meta:
        model = AdminAddress
        fields = ('street1', 'street2', 'city', 'state_id', 'country_id', 'label', 'number','zip_code', 'is_default',
                  'is_active', )
        extra_kwargs = {
            "zip_code": {
                "error_messages": {
                    "max_length": INVALID_ZIP_CODE_NUMBER_LENGTH
                }
            },
            "number": {
                "error_messages": {
                    "max_length": INVALID_NUMBER_LENGTH
                }
            }
        }

    def validate_number(self, value):
        # validate phone number
        validate_phone_number(value, 'number')
        return value

    def validate_zip_code(self, value):
        # validate zip code number
        validate_zip_code(value)
        return value

    def validate(self, attrs):
        errors = {}

        # check extra fields in payload, if found raise an error message
        if hasattr(self, 'initial_data'):
            extra_fields = set(self.initial_data.keys()) - set(self.fields.keys())
            if extra_fields:
                extra_fields = ", ".join(extra_fields)
                errors.setdefault("message", []).append(EXTRA_FIELDS_IN_PAYLOAD.format(extra_fields))

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

        filter_kwargs = {'created_by': self.context['request'].user.id, 'is_default': True}

        # validate admin default address
        validated_data = self._check_default_address_exits(AdminAddress, validated_data, filter_kwargs)

        # add new address
        instance = AdminAddress.objects.create(**validated_data)
        return instance

    def update(self, instance, validated_data):
        validated_data['updated_by'] = self.context['request'].user

        filter_kwargs = {'created_by': instance.created_by.id, 'is_default': True}

        # validate admin default address
        validated_data = self._check_default_address_exits(AdminAddress, validated_data, filter_kwargs)

        # setter to set instance value
        for key, item in validated_data.items():
            setattr(instance, key, item)

        instance.updated_on = timezone.now()

        # saved updated admin address value
        instance.save()

        return instance
