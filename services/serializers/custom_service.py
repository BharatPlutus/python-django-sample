from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from common_config.api_message import EXTRA_FIELDS_IN_PAYLOAD
from services.models.custom_service import CustomService


class CustomServiceViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomService
        fields = '__all__'


class CustomServiceFilterListSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomService
        fields = '__all__'

    def to_representation(self, instance):
        data = super(CustomServiceFilterListSerializer, self).to_representation(instance)
        return data


class CustomServiceListSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomService
        fields = '__all__'

    def to_representation(self, instance):
        data = super(CustomServiceListSerializer, self).to_representation(instance)
        return data


class CustomServiceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomService
        fields = ("name", "short_description", "description", "price", "vendor_id",)

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

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user

        # create new service
        instance = CustomService.objects.create(**validated_data)
        return instance


class CustomServiceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomService
        fields = ("name", "short_description", "description", "price",)

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

    def update(self, instance, validated_data):
        for key, item in validated_data.items():
            setattr(instance, key, item)

        instance.updated_on = timezone.now()
        instance.updated_by = self.context['request'].user
        instance.save()

        return instance
