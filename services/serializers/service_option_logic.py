from rest_framework import serializers

from common_config.api_message import REQUIRED_FIELD, NOT_FOUND_JSON_DATA, INVALID_SERVICE_OPTION_LOGIC_COMPARE_TO

from services.models.service_option_logic import ServiceOptionAction, ServiceOptionRule


class ServiceOptionRuleSerializer(serializers.ModelSerializer):
    option_action_id = serializers.PrimaryKeyRelatedField(read_only=True)
    compare_option_field = serializers.IntegerField(required=True)

    class Meta:
        model = ServiceOptionRule
        fields = '__all__'

    def validate(self, attrs):
        errors = {}

        if "operator_type" not in attrs:
            errors.setdefault("operator_type", []).append(REQUIRED_FIELD)

        if "compare_to" not in attrs:
            errors.setdefault("compare_to", []).append(REQUIRED_FIELD)

        if "compare_option_field" not in attrs:
            errors.setdefault("compare_option_field", []).append(REQUIRED_FIELD)

        if "operator_type" in attrs and attrs["operator_type"] in ['>=', '<=', '<', '>', '!=']:
            if "compare_to" in attrs and not attrs['compare_to'].isnumeric():
                errors.setdefault("compare_to", []).append(
                    INVALID_SERVICE_OPTION_LOGIC_COMPARE_TO.format(attrs['compare_to']))

        if len(errors) > 0:
            raise serializers.ValidationError(errors)

        return attrs


class ServiceOptionRuleViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceOptionRule
        fields = '__all__'


class ServiceOptionLogicViewSerializer(serializers.ModelSerializer):
    rules = ServiceOptionRuleViewSerializer(many=True)

    class Meta:
        model = ServiceOptionAction
        fields = ("id", "apply_to_option_id", "action", "conditional_join", "conditional_logic", "rules")


class ServiceOptionLogicSerializer(serializers.ModelSerializer):
    rules = ServiceOptionRuleSerializer(many=True)
    apply_to_option_id = serializers.IntegerField(required=True)

    class Meta:
        model = ServiceOptionAction
        fields = '__all__'

    def validate(self, attrs):
        errors = {}
        if "action" not in attrs:
            errors.setdefault("action", []).append(REQUIRED_FIELD)

        if "conditional_join" not in attrs:
            errors.setdefault("conditional_join", []).append(REQUIRED_FIELD)

        if "conditional_join" not in attrs:
            errors.setdefault("conditional_join", []).append(REQUIRED_FIELD)

        if "apply_to_option_id" not in attrs:
            errors.setdefault("apply_to_option_id", []).append(REQUIRED_FIELD)

        if "rules" not in attrs:
            errors.setdefault("rules", []).append(REQUIRED_FIELD)

        if "rules" in attrs and len(attrs['rules']) <= 0:
            errors.setdefault("rules", []).append(NOT_FOUND_JSON_DATA)

        if len(errors) > 0:
            raise serializers.ValidationError(errors)

        return attrs
