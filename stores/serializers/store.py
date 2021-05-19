from django.utils import timezone
from django.contrib.auth.models import Group
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from common_config.api_message import ZERO_DECIMAL_VALUE, EXTRA_FIELDS_IN_PAYLOAD, NOT_FOUND_JSON_DATA, \
    INVALID_STORE_PORTAL_URL, REQUIRED_FIELD, BLANK_FIELD, DUPLICATE_WHITE_LABEL_DOMAIN
from common_config.constant import STORE_OWNER_ROLE, AWS_DNS_NAME, THEME_TOP_BAR_COLOR, THEME_BORDER_COLOR, \
    THEME_BUTTON_COLOR, THEME_BACKGROUND_COLOR
from shippings.serializers.easypost.helper import PREDEFINE_SHIPPING_RATE_OPTION
from utils.aws_route_53 import SubDomain
from utils.custom_validators.url import url_validator
from utils.custom_validators.phone_number import validate_phone_number
from utils.fields.base64_image_field import Base64ImageField

from stores.models.store_setting import StoreSetting
from insurances.serializers.insurance import InsuranceViewSerializer
from stores.models.store import Store
from users.models.profile import UserProfile
from price_groups.models.price_group import StorePriceGroup, PriceGroup
from users.serializers.store_user_profile import StoreUserProfileSerializer
from price_groups.tasks.store_service import connect_services_to_store_task, enable_or_disable_store_service_price_task
from stores.task.white_label_setup import create_nginx_server_setup_task


class StoreOwnerLoginSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ('id', 'name', 'url', 'first_name', 'last_name', 'is_repair_shop',
                  'website_url', 'is_complete_white_label', 'white_label_domain', 'is_onboarding_complete',)

    def to_representation(self, instance):
        data = super(StoreOwnerLoginSerializer, self).to_representation(instance)
        try:
            data['price_group_id'] = instance.price_group.price_group_id.id
        except Exception as err:
            data['price_group_id'] = None
        return data


class StoreNestedViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ('id', 'name', 'first_name', 'last_name', 'public_email', 'public_phone', 'website_url',)


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ('id', 'name', 'url', 'first_name', 'last_name', 'public_email', 'public_phone', 'is_repair_shop',
                  'website_url', 'is_complete_white_label', 'white_label_domain',)


class StoreRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = '__all__'

    def to_representation(self, instance):
        data = super(StoreRetrieveSerializer, self).to_representation(instance)
        try:
            data['price_group_id'] = instance.price_group.price_group_id.id
        except Exception as err:
            data['price_group_id'] = None
        return data


class StoreListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = '__all__'

    def to_representation(self, instance):
        data = super(StoreListSerializer, self).to_representation(instance)
        try:
            data['price_group_id'] = instance.price_group.price_group_id.id
        except Exception as err:
            data['price_group_id'] = None
        return data


class StoreViewSerializer(serializers.ModelSerializer):
    insurance = InsuranceViewSerializer(source="insurance_id")

    class Meta:
        model = Store
        fields = "__all__"

    def to_representation(self, instance):
        data = super(StoreViewSerializer, self).to_representation(instance)
        try:
            data['price_group_id'] = instance.price_group.price_group_id.id
        except Exception as err:
            data['price_group_id'] = None

        store_owner_list = instance.profile.filter(is_owner=True, is_active=True)

        if len(store_owner_list) > 0:
            owner = store_owner_list[0]
            data['user'] = dict(username=owner.user.username, is_active=owner.is_active, is_owner=owner.is_owner)

        if "insurance" in data:
            if data['insurance'] is not None and "stores" in data['insurance']:
                del data['insurance']['stores']

            del data['insurance_id']

        from stores.serializers.white_label_setting import StoreSettingViewSerializer
        data['setting'] = StoreSettingViewSerializer(instance.settings).data

        return data


class StoreSerializerMixin(serializers.ModelSerializer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.val_errors = {}

    def validate_website_url(self, value):
        # validate store website url
        url_validator(value)
        return value

    def validate_public_phone(self, value):
        # validate public phone number
        validate_phone_number(value, 'public phone number')
        return value

    def validate_owner_phone(self, value):
        # validate owner phone number
        validate_phone_number(value, 'owner phone number')
        return value

    def validate_white_label_url(self, value):
        # validate store website url
        url_validator(value)
        return value

    def validate_white_label_url_unique(self, value):
        white_label_url = []
        try:
            white_label_url = Store.objects.filter(white_label_domain=value)
        except Exception as err:
            self.val_errors.setdefault("white_label_domain", []).append(err.args[0])

        if white_label_url:
            self.val_errors.setdefault("white_label_domain", []).append(DUPLICATE_WHITE_LABEL_DOMAIN.format(value))


class StoreCreateSerializer(StoreSerializerMixin):
    user = StoreUserProfileSerializer(required=True)
    use_platform_shipping = serializers.BooleanField(required=False)
    top_up_amount = serializers.DecimalField(required=False, max_digits=20, decimal_places=2)
    logo = Base64ImageField(allow_empty_file=False, allow_null=False, required=True)
    price_group_id = serializers.PrimaryKeyRelatedField(queryset=PriceGroup.objects.all(), required=False)

    class Meta:
        model = Store
        fields = '__all__'

    def validate(self, attrs):
        # check extra fields in payload, if found raise an error message
        if hasattr(self, 'initial_data'):
            extra_fields = set(self.initial_data.keys()) - set(self.fields.keys())
            if extra_fields:
                extra_fields = ", ".join(extra_fields)
                self.val_errors.setdefault("message", []).append(EXTRA_FIELDS_IN_PAYLOAD.format(extra_fields))

        # validate subscription fee must be greater than 0
        if 'subscription_fee' in attrs:
            if attrs['subscription_fee'] < 0:
                self.val_errors.setdefault("subscription_fee", []).append(
                    ZERO_DECIMAL_VALUE.format(attrs['subscription_fee']))

        if "user" in attrs and len(attrs['user']) <= 0:
            self.val_errors.setdefault("user", []).append(NOT_FOUND_JSON_DATA)

        if "subdomain" in attrs and "url" in attrs:
            # create temp url
            temp_url = "{0}.{1}".format(attrs['subdomain'], AWS_DNS_NAME)

            if temp_url != attrs['url']:
                self.val_errors.setdefault("url", []).append(INVALID_STORE_PORTAL_URL.format(attrs['url']))

        if "is_complete_white_label" in attrs and attrs['is_complete_white_label']:
            if "white_label_url" not in attrs:
                self.val_errors.setdefault("white_label_url", []).append(REQUIRED_FIELD)

            elif "white_label_url" in attrs and attrs['white_label_url'] == "":
                self.val_errors.setdefault("white_label_url", []).append(BLANK_FIELD)

            elif "white_label_url" in attrs:
                self.validate_white_label_url_unique(attrs['white_label_url'])

        if self.val_errors:
            raise ValidationError(self.val_errors)

        return attrs

    def create(self, validated_data):
        user = None
        settings = {}
        price_group_id = validated_data.pop("price_group_id", None)

        if "top_up_amount" in validated_data:
            settings['top_up_amount'] = validated_data.pop("top_up_amount")

        if "use_platform_shipping" in validated_data:
            settings['use_platform_shipping'] = validated_data.pop("use_platform_shipping")

        if "logo" in validated_data:
            settings['logo'] = validated_data.pop("logo")

        if "user" in validated_data:
            # set store url name
            validated_data['user']['domain'] = validated_data['url']
            user = validated_data.pop("user")

        # get current login user object from context and set in create_by and updated_by
        validated_data['created_by'] = self.context['request'].user
        validated_data['is_onboarding_complete'] = False

        # create new store
        instance = Store.objects.create(**validated_data)

        include_fields = ['first_name', 'last_name']
        if user is not None and len(user) > 0:
            for key, item in validated_data.items():
                if key in include_fields:
                    user[key] = item
                if key == "owner_email":
                    user['email'] = item

            # create auth user
            # create user
            user_instance = self.fields['user'].create(user)

            store_user_profile = dict(user=user_instance, store_id=instance, is_owner=True,
                                      created_by=self.context['request'].user)

            # assign default store owner group
            store_group = Group.objects.get(name=STORE_OWNER_ROLE)
            user_instance.groups.add(store_group)

            # create store login user profile
            UserProfile.objects.create(**store_user_profile)

        # create store setting payload
        settings_payload = dict(store_id=instance, top_bar_color=THEME_TOP_BAR_COLOR,
                                button_color=THEME_BUTTON_COLOR, border_color=THEME_BORDER_COLOR,
                                background_color=THEME_BACKGROUND_COLOR)

        if settings:
            settings_payload.update(settings)

        # create store settings
        StoreSetting.objects.create(**settings_payload)

        # create store sub domain on AWS 53 route and map with store
        create_sub_domain = SubDomain()
        create_sub_domain.save(validated_data['subdomain'], validated_data['name'])

        if "white_label_domain" in validated_data:
            # create nginx server setup
            create_nginx_server_setup_task.delay({'white_label_domain': validated_data['white_label_domain']})

        if price_group_id is not None:
            # store price group record
            StorePriceGroup.objects.create(store_id=instance, price_group_id=price_group_id,
                                           created_by=self.context['request'].user)

        return instance


class StoreUpdateSerializer(StoreSerializerMixin):
    SHIPPING_ACCOUNT_CHOICES = (
        (1, "Fedex"),
        (2, "UspsAccount"),
        (3, "UpsAccount"),
    )

    user = StoreUserProfileSerializer(required=True)
    use_platform_shipping = serializers.BooleanField(required=False)
    top_up_amount = serializers.DecimalField(required=False, max_digits=20, decimal_places=2)
    shipping_account_type = serializers.ChoiceField(choices=SHIPPING_ACCOUNT_CHOICES, required=False)
    is_disable_price = serializers.BooleanField(required=False)
    is_repair_step = serializers.BooleanField(required=False)
    price_group_id = serializers.PrimaryKeyRelatedField(queryset=PriceGroup.objects.all(), required=False)

    class Meta:
        model = Store
        fields = '__all__'
        read_only_fields = ('subdomain', 'url', 'created_on', 'created_by',)

    def validate(self, attrs):
        # check extra fields in payload, if found raise an error message
        if hasattr(self, 'initial_data'):
            extra_fields = set(self.initial_data.keys()) - set(self.fields.keys())
            if extra_fields:
                extra_fields = ", ".join(extra_fields)
                self.val_errors.setdefault("message", []).append(EXTRA_FIELDS_IN_PAYLOAD.format(extra_fields))

        # validate subscription fee must be greater than 0
        if 'subscription_fee' in attrs:
            if attrs['subscription_fee'] == 0:
                self.val_errors.setdefault("subscription_fee", []).append(
                    ZERO_DECIMAL_VALUE.format(attrs['subscription_fee']))

        if "user" in attrs and len(attrs['user']) <= 0:
            self.val_errors.setdefault("user", []).append(NOT_FOUND_JSON_DATA)

        if "is_complete_white_label" in attrs and attrs['is_complete_white_label']:
            if "white_label_domain" not in attrs:
                self.val_errors.setdefault("white_label_domain", []).append(REQUIRED_FIELD)

            elif "white_label_domain" in attrs and attrs['white_label_domain'] == "":
                self.val_errors.setdefault("white_label_domain", []).append(BLANK_FIELD)

            elif "white_label_domain" in attrs:
                self.validate_white_label_url_unique(attrs['white_label_domain'])

        if self.val_errors:
            raise ValidationError(self.val_errors)

        return attrs

    def update(self, instance, validated_data):
        user = None
        settings = {}
        price_group_id = validated_data.pop("price_group_id", "")

        if "shipping_account_type" in validated_data:
            settings['shipping_account_type'] = validated_data.pop("shipping_account_type")

        if "top_up_amount" in validated_data:
            settings['top_up_amount'] = validated_data.pop("top_up_amount")

        if "use_platform_shipping" in validated_data:
            settings['use_platform_shipping'] = validated_data.pop("use_platform_shipping")

        if "is_disable_price" in validated_data:
            settings['is_disable_price'] = validated_data.pop("is_disable_price")

        if "user" in validated_data:
            user = validated_data.pop("user")

        if "is_repair_step" in validated_data:
            settings['is_repair_step'] = validated_data.pop("is_repair_step")

        # set current login user object
        validated_data['updated_by'] = self.context['request'].user

        # set store field value
        for key, item in validated_data.items():
            setattr(instance, key, item)

        instance.updated_on = timezone.now()

        # update instance
        instance.save()

        # update user if is not none
        if user is not None and len(user) > 0:
            store_user_profile = instance.profile.filter(is_owner=True)

            if store_user_profile:
                # update store login user name and password
                self.fields['user'].update(store_user_profile[0].user, user)

                # update store user table
                store_user_profile[0].updated_on = timezone.now()
                store_user_profile[0].updated_by = self.context['request'].user

                store_user_profile[0].save()

        if settings:
            for key, value in settings.items():
                setattr(instance.settings, key, value)

            # update store settings
            instance.settings.save()

        if price_group_id is not None and price_group_id != "":
            # system user update store service
            connect_services_to_store_task.delay({'price_group_id': price_group_id.id,
                                                  'store_id': instance.id})

        if "is_disable_price" in settings:
            try:
                instance.price_group.price_group_id
            except Exception as err:
                pass
            else:
                storeServicePricePayload = {'price_group_id': instance.price_group.price_group_id.id,
                                            'store_id': instance.id,
                                            'is_disable_price': settings['is_disable_price']}

                # system user update store service price
                enable_or_disable_store_service_price_task.delay(storeServicePricePayload)

        if "white_label_domain" in validated_data:
            # create nginx server setup
            create_nginx_server_setup_task.delay({'white_label_domain': validated_data['white_label_domain']})

        if price_group_id is None:
            try:
                instance.price_group.id.delete()
            except Exception as err:
                pass

        if "shipping_account_type" in settings:
            carrierObj = instance.carriers.filter(account_type=settings['shipping_account_type'], is_active=True)

            if carrierObj:
                from shippings.models.easypost.carrier_account import ShippingRateOption
                # create shipping rate option object
                rateOptionPayload = dict(store_id=instance, carrier_id=carrierObj[0],
                                         rate_options=PREDEFINE_SHIPPING_RATE_OPTION[carrierObj[0].account_type][
                                             'options'],
                                         created_by=self.context['request'].user)
                ShippingRateOption.objects.create(**rateOptionPayload)

        return instance


class StoreGetStartedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = '__all__'
        read_only_fields = ('subdomain', 'url', 'created_on', 'created_by',)

    def get_started(self, instance):
        instance.updated_by = self.context['request'].user
        instance.updated_on = timezone.now()
        instance.is_onboarding_complete = True

        # update store
        instance.save()

        return instance