import ast
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from common_config.constant import DEFAULT_WARRANTY_METADATA
from common_config.serializers.image import ImageCreateBulkSerializer, ImageUpdateBulkSerializer, ImageSerializer
from common_config.models.image import Image
from common_config.api_message import EXTRA_FIELDS_IN_PAYLOAD, REQUIRED_FIELD, INVALID_SERVICE_OPTION_ID, \
    INVALID_SERVICE_OPTION_IMAGE_ID, NOT_FOUND_JSON_DATA, INVALID_SERVICE_OPTION_LOGIC_COMPARE_FIELD_VALUE, \
    INVALID_SERVICE_OPTION_LOGIC_APPLY_OPTION_FIELD_ID, INVALID_OPTION_WARRANTY_METADATA

from services.models.service_option import ServiceOption
from services.models.service_option_logic import ServiceOptionAction, ServiceOptionRule
from services.serializers.service_option_logic import ServiceOptionLogicSerializer, ServiceOptionLogicViewSerializer
from price_groups.models.price_group_service_option import PriceGroupServiceOption


class ServiceOptionSerializerSuperAdminMixin(serializers.ModelSerializer):
    images = ImageSerializer(many=True)

    class Meta:
        model = ServiceOption
        fields = '__all__'


class ServiceOptionSerializerCustomerPortalMixin(serializers.ModelSerializer):
    images = ImageSerializer(many=True)
    option_logic = ServiceOptionLogicViewSerializer(many=True)

    class Meta:
        model = ServiceOption
        fields = ('images', 'instruction', 'is_metal_type', 'is_required', 'option_logic', 'tool_tips',)
        read_only_fields = fields


class ServiceOptionViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceOption
        fields = '__all__'

    def to_representation(self, instance):
        data = super(ServiceOptionViewSerializer, self).to_representation(instance)

        if instance.field_type in [5, 6, 10, 11]:
            label_list = ast.literal_eval(instance.field_text1)
            data['field_text1'] = ",".join(label_list)

        return data


class ServiceOptionListSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True)
    option_logic = ServiceOptionLogicViewSerializer(many=True)

    class Meta:
        model = ServiceOption
        fields = '__all__'

    def to_representation(self, instance):
        data = super(ServiceOptionListSerializer, self).to_representation(instance)

        if instance.field_type in [5, 6, 10, 11]:
            label_list = ast.literal_eval(instance.field_text1)
            data['field_text1'] = ",".join(label_list)

        return data


class ServiceOptionBulkCreateUpdateSerializer(serializers.ListSerializer):

    @staticmethod
    def create_or_update_option_images(images, instance):
        """
        Create or update service option images
        :param images:
        :param instance:
        :return:
        """
        create_images = []
        update_images = []
        delete_image = []
        image_ids = []

        for image in images:
            if "POST" in image['method']:
                del image['method']
                create_images.append(image)
            elif "PUT" in image['method']:
                del image['method']
                update_images.append(image)
            else:
                delete_image.append(image['id'])

        if len(create_images) > 0:
            # add service option image
            img_instances = Image.upload_new_images(*create_images)
            image_ids.extend(img_instances)

        if len(update_images) > 0:
            # update service option image
            img_instances = Image.update_existing_images(*update_images)
            image_ids.extend(img_instances)

        if len(delete_image) > 0:
            Image.delete_bulk_images(delete_image)

        # set reference service option images ids
        instance.images.add(*image_ids)

        # add/update price list service option images
        # TODO

    def create(self, validated_data):
        """
        Create service option
        :param validated_data:
        :return:
        """
        option_sequence_mapping = {}
        option_logic_rules = []
        createOptionIds = []

        for option in validated_data:
            images = option.pop("option_images", None)
            option_logic = option.pop("option_logic", None)
            sequence = option.get("sequence")

            if "method" in option:
                del option['method']

            if "field_text1" in option and 'field_type' in option and option['field_type'] in [5, 6, 10, 11]:
                label_list = option['field_text1'].split(",")
                field_text1 = {label: "" for label in label_list}
                option['field_text1'] = str(field_text1)

            if "meta_data" not in option and 'field_type' in option and option['field_type'] in [12]:
                option['meta_data'] = DEFAULT_WARRANTY_METADATA

            # create service option
            instance = ServiceOption.objects.create(**option)

            option_sequence_mapping[sequence] = instance

            if instance.field_type in [12]:
                createOptionIds.append(instance.id)

            if option_logic is not None:
                option_logic_rules.append(option_logic)

            if images is not None:
                self.create_or_update_option_images(images, instance)

        if createOptionIds:
            self.context['request'].session['createOptionIds'] = createOptionIds

        # if len(option_logic_rules) > 0 and len(option_sequence_mapping) > 0:
        #     self.create_service_option_logic()
        return option_logic_rules, option_sequence_mapping

    @staticmethod
    def create_logic_query(logic_query, conditional_join, operator_type, compare_to, is_last):
        """
        :param logic_query:
        :param conditional_join:
        :param operator_type:
        :param compare_to:
        :param is_last:
        :return:
        """
        conditional_join_reg = {'all': 'and', 'none': 'and', 'one': 'or'}
        logic_query = "{0} compare_option_field {1} '{2}'".format(logic_query, operator_type, compare_to)

        if not is_last:
            logic_query = "{0} {1}".format(logic_query, conditional_join_reg[conditional_join])
        return logic_query

    def create_service_option_rules(self, rules, option_sequence_mapping, action_instance):
        """
        :param rules:
        :param option_sequence_mapping:
        :param action_instance:
        :return:
        """
        logic_query = "where "
        is_last = False
        errors = []

        for idx, rule in enumerate(rules, start=1):
            rule['option_action_id'] = action_instance
            rule_error = {}

            # validate service option sequence number with compare_option_field if not match raise error message
            if rule['compare_option_field'] not in option_sequence_mapping:
                rule_error.setdefault("compare_option_field", []).append(
                    INVALID_SERVICE_OPTION_LOGIC_COMPARE_FIELD_VALUE.format(rule['compare_option_field']))
                errors.append(rule_error)
                continue

            # replace database id to sequence number
            rule['compare_option_field'] = option_sequence_mapping[rule['compare_option_field']]

            # add new service option action rules
            ServiceOptionRule.objects.create(**rule)

            if len(rules) == idx:
                is_last = True

            # create option logic query
            logic_query = self.create_logic_query(logic_query, action_instance.conditional_join,
                                                  rule['operator_type'], rule['compare_to'], is_last)

        if len(errors) > 0:
            raise serializers.ValidationError({'options': [{'option_logic': [{'rules': [errors]}]}]})

        action_instance.conditional_logic = logic_query
        action_instance.save()

    def create_service_option_logic(self, option_sequence_mapping, option_logic_rules):
        """
        :param option_sequence_mapping:
        :param option_logic_rules:
        :return:
        """
        errors = {}

        for option_logics in option_logic_rules:
            for action in option_logics:
                rules = action.pop("rules")

                # validate service option sequence number with apply_to_option_id if not match raise error message
                if action['apply_to_option_id'] not in option_sequence_mapping:
                    errors.setdefault("apply_to_option_id", []).append(
                        INVALID_SERVICE_OPTION_LOGIC_APPLY_OPTION_FIELD_ID.format(action['apply_to_option_id']))
                    continue

                # replace database id to sequence number
                action['apply_to_option_id'] = option_sequence_mapping[action['apply_to_option_id']]

                # delete old service option logic rules
                old_option_logic_rules = action['apply_to_option_id'].option_logic.all()
                if len(old_option_logic_rules) > 0:
                    for old_option_logic_rule in old_option_logic_rules:
                        old_option_logic_rule.delete()

                # add new service option action
                action_instance = ServiceOptionAction.objects.create(**action)

                # add new service option action rules
                self.create_service_option_rules(rules, option_sequence_mapping, action_instance)

        if len(errors) > 0:
            raise serializers.ValidationError({'options': [{'option_logic': [errors]}]})

    @staticmethod
    def add_or_update_price_group_service_option_images(instance, images):
        # un-reference all old data
        instance.images.clear()

        if len(images) > 0:
            # add/update price group service option images
            instance.images.add(*images)

    def update_store_option_label(self, price_group_service_option, new_field_text1):
        store_service_option = price_group_service_option.store_service_option.all()

        for str_option_obj in store_service_option:
            old_field_text1 = ast.literal_eval(str_option_obj.field_text1)
            str_option_obj.field_text1 = self.transform_option_label(old_field_text1, new_field_text1)
            str_option_obj.save()

    def transform_option_label(self, old_field_text1, new_field_text1):
        new_dict = {}
        added, removed = self.compare_field_text1(old_field_text1, new_field_text1)

        for key1, value1 in old_field_text1.items():
            update_key = key1
            update_value = value1

            if key1 in removed:
                for key2, value2 in new_field_text1.items():
                    if key2 in key1 and key2 not in old_field_text1:
                        update_key = key2

            new_dict[update_key] = update_value

        for add_key in added:
            if add_key not in new_dict:
                new_dict[add_key] = ""

        for del_key in removed:
            if del_key in new_dict:
                del new_dict[del_key]

        return str(new_dict)

    @staticmethod
    def compare_field_text1(field_test1_old, field_test1_new):
        field_test1_old_keys = set(field_test1_old.keys())
        field_test1_new_keys = set(field_test1_new.keys())
        removed = field_test1_old_keys - field_test1_new_keys
        added = field_test1_new_keys - field_test1_old_keys

        return list(added), list(removed)

    def update_price_list_service_option(self, instance, updated_price_list_option_payload, images):
        # get all service option related price list service options
        price_group_service_options = PriceGroupServiceOption.objects.filter(service_option_id=instance.id)

        for price_group_service_option in price_group_service_options:

            if "field_text1" in updated_price_list_option_payload and instance.field_type in [5, 6, 10, 11] and \
                    price_group_service_option.field_type in [5, 6, 10, 11]:
                field_text1 = ast.literal_eval(price_group_service_option.field_text1)
                # compare service option field_text1 value to price list service option field_text1 value
                price_group_service_option.field_text1 = self.transform_option_label(field_text1,
                                                                                     updated_price_list_option_payload[
                                                                                         'field_text1'])

                # update all store service option
                self.update_store_option_label(price_group_service_option,
                                               updated_price_list_option_payload['field_text1'])

                del updated_price_list_option_payload['field_text1']

            # set key and items
            for key, item in updated_price_list_option_payload.items():
                setattr(price_group_service_option, key, item)

            # update price list service option
            price_group_service_option.save()

            if images is not None:
                self.add_or_update_price_group_service_option_images(price_group_service_option, images)

    def update_bulk_records(self, validated_data):
        """
        Update service option
        :param validated_data:
        :return:
        """

        option_sequence_mapping = {}
        option_logic_rules = []

        for option in validated_data:

            option_id = option.pop("id").id
            service_id = option.pop("service_id").id
            images = option.pop("option_images", None)
            option_logic = option.pop("option_logic", None)
            sequence = option.get("sequence")

            if "method" in option:
                del option['method']

            # get service option object
            instance = ServiceOption.objects.get(pk=option_id, service_id=service_id)

            option_sequence_mapping[sequence] = instance

            if option_logic is not None:
                option_logic_rules.append(option_logic)

            if images is not None:
                self.create_or_update_option_images(images, instance)

            updated_price_list_option_payload = dict()

            if "other_option" in option:
                updated_price_list_option_payload['other_option'] = option['other_option']

            if "other_option_value" in option:
                updated_price_list_option_payload['other_option_value'] = option['other_option_value']

            if "field_text2" in option:
                updated_price_list_option_payload['field_text2'] = option['field_text2']

            if "field_text1" in option and instance.field_type in [5, 6, 10, 11]:
                label_list = option['field_text1'].split(",")
                field_text1 = {label: "" for label in label_list}
                updated_price_list_option_payload['field_text1'] = field_text1
                option['field_text1'] = str(field_text1)

            elif "field_text1" in option:
                updated_price_list_option_payload['field_text1'] = option['field_text1']

            if "sequence" in option and instance.sequence != option['sequence']:
                updated_price_list_option_payload['sequence'] = option['sequence']

            if "field_date" in option and instance.field_type in [12]:
                updated_price_list_option_payload['field_date'] = option['field_date']

            if "meta_data" in option and instance.field_type in [12]:
                updated_price_list_option_payload['meta_data'] = option['meta_data']

            # set key and items
            for key, item in option.items():
                setattr(instance, key, item)

            instance.updated_on = timezone.now()

            # update service option
            instance.save()

            if len(updated_price_list_option_payload) > 0:
                updated_images = instance.images.all() if images is not None else None

                self.update_price_list_service_option(instance, updated_price_list_option_payload, updated_images)

        return option_logic_rules, option_sequence_mapping


class ServiceOptionSerializerMixin(serializers.ModelSerializer):

    def validate(self, attrs):
        errors = {}

        # check extra fields in payload, if found raise an error message
        if hasattr(self, 'initial_data'):

            for data in self.initial_data:
                extra_fields = set(data.keys()) - set(self.fields.keys())
                if extra_fields:
                    extra_fields = ", ".join(extra_fields)
                    errors.setdefault("message", []).append(EXTRA_FIELDS_IN_PAYLOAD.format(extra_fields))

        if "option_images" in attrs:
            if len(attrs['option_images']) <= 0:
                errors.setdefault("option_images", []).append(NOT_FOUND_JSON_DATA)

        if "option_logic" in attrs:
            if len(attrs['option_logic']) <= 0:
                errors.setdefault("option_logic", []).append(NOT_FOUND_JSON_DATA)

        if "sequence" not in attrs:
            errors.setdefault("sequence", []).append(REQUIRED_FIELD)

        if "method" in attrs and attrs['method'] == "PUT":
            if "id" not in attrs:
                errors.setdefault("id", []).append(REQUIRED_FIELD)

            # if "field_type" in attrs:
            #     errors.setdefault("field_type", []).append(EXTRA_FIELDS_IN_PAYLOAD.format("field_type"))

            # validate service option ids
            if "id" in attrs:
                service_options_ids = [x.id for x in attrs['service_id'].options.all()]
                if attrs['id'].id not in service_options_ids:
                    errors.setdefault("id", []).append(INVALID_SERVICE_OPTION_ID.format(attrs['id'].id))

                # validate service option images ids
                if "option_images" in attrs:
                    images = attrs['option_images']

                    service_option_images_ids = [x.id for x in attrs['id'].images.all()]

                    for img in images:
                        if "method" in img and img['method'] in ["PUT", "DELETE"]:
                            if img['id'].id not in service_option_images_ids:
                                errors.setdefault("option_images", []).append(
                                    {'id': [INVALID_SERVICE_OPTION_IMAGE_ID.format(img['id'].id)]})

                if attrs['id'].field_type in [12]:
                    if "meta_data" in attrs and isinstance(attrs['meta_data'], dict):
                        meta_keys = list(attrs['meta_data'].keys())
                        invalid_meta_key = False
                        for xx in meta_keys:
                            if xx not in ['in_warranty', 'not_in_warranty', 'months_limit', 'warranty_date_label']:
                                invalid_meta_key = True
                                break
                        if invalid_meta_key:
                            errors.setdefault("meta_data", []).append(INVALID_OPTION_WARRANTY_METADATA)
        else:
            if "field_type" in attrs and attrs['field_type'] in [12]:
                if "meta_data" in attrs and isinstance(attrs['meta_data'], dict):
                    meta_keys = list(attrs['meta_data'].keys())
                    invalid_meta_key = False
                    for xx in meta_keys:
                        if xx not in ['in_warranty', 'not_in_warranty', 'months_limit', 'warranty_date_label']:
                            invalid_meta_key = True
                            break
                    if invalid_meta_key:
                        errors.setdefault("meta_data", []).append(INVALID_OPTION_WARRANTY_METADATA)

        if len(errors) > 0:
            raise ValidationError(errors)

        return attrs


class ServiceOptionCreateSerializer(ServiceOptionSerializerMixin):
    METHOD_CHOICE = (
        ('POST', 'POST'),
    )

    service_id = serializers.PrimaryKeyRelatedField(read_only=True)
    option_images = ImageCreateBulkSerializer(many=True, read_only=False, allow_null=False, required=False)
    method = serializers.ChoiceField(choices=METHOD_CHOICE, required=True)
    sequence = serializers.IntegerField(required=True)
    option_logic = ServiceOptionLogicSerializer(many=True, read_only=False, allow_null=False, required=False)

    class Meta:
        model = ServiceOption
        fields = ("name", "method", "option_images", "is_active", "service_id", "status", "field_type", "instruction",
                  "tool_tips", "is_required", "other_option", "other_option_value", "field_text1", "field_text2",
                  "sequence", "option_logic", "is_metal_type", "field_date", "meta_data",)

        list_serializer_class = ServiceOptionBulkCreateUpdateSerializer


class ServiceOptionUpdateSerializer(ServiceOptionSerializerMixin):
    METHOD_CHOICE = (
        ('POST', 'POST'),
        ('PUT', 'PUT'),
    )

    id = serializers.PrimaryKeyRelatedField(queryset=ServiceOption.objects.all())
    option_images = ImageUpdateBulkSerializer(many=True, read_only=False, allow_null=False, required=False)
    method = serializers.ChoiceField(choices=METHOD_CHOICE, required=True)
    sequence = serializers.IntegerField(required=True)
    option_logic = ServiceOptionLogicSerializer(many=True, read_only=False, allow_null=False, required=False)

    class Meta:
        model = ServiceOption
        fields = (
            "id", "method", "name", "option_images", "is_active", "service_id", "status", "field_type", "instruction",
            "tool_tips", "is_required", "other_option", "other_option_value", "field_text1", "field_text2", "sequence",
            "option_logic", "is_metal_type", "field_date", "meta_data",)

        list_serializer_class = ServiceOptionBulkCreateUpdateSerializer
