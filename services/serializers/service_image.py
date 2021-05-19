from rest_framework import serializers

from common_config.api_message import LARGE_IMAGE_SIZE, NOT_SELECTED_FILE, EXTRA_FIELDS_IN_PAYLOAD, REQUIRED_FIELD
from common_config.models.image import Image
from utils.fields.base64_image_field import Base64ImageField


class ServiceImageAddSerializer(serializers.ModelSerializer):
    image = Base64ImageField(allow_empty_file=False, allow_null=False, required=True)

    class Meta:
        model = Image
        fields = ("image", )

    def validate(self, attrs):
        errors = {}

        # check extra fields in payload, if found raise an error message
        if hasattr(self, 'initial_data'):
            extra_fields = set(self.initial_data.keys()) - set(self.fields.keys())
            if extra_fields:
                extra_fields = ", ".join(extra_fields)
                errors.setdefault("message", []).append(EXTRA_FIELDS_IN_PAYLOAD.format(extra_fields))

        if "image" not in attrs:
            errors.setdefault("image", []).append(REQUIRED_FIELD)

        # validate image size
        if 'image' in attrs:
            limit = 1024 * 1024 * 10

            if attrs['image'] is None:
                errors.setdefault("image", []).append(NOT_SELECTED_FILE)

            elif attrs['image'].size > limit:
                errors.setdefault("image", []).append(LARGE_IMAGE_SIZE)

        if len(errors) > 0:
            raise serializers.ValidationError(errors)

        return attrs