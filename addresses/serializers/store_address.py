from django.contrib.auth.models import Permission
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.serializers import ValidationError

from common_config.api_message import INVALID_ZIP_CODE_NUMBER_LENGTH, INVALID_NUMBER_LENGTH, EXTRA_FIELDS_IN_PAYLOAD, \
    REQUIRED_FIELD
from users.utils.permission import mapped_staff_group_django_permission_json
from utils.custom_validators.zip_code import validate_zip_code
from utils.custom_validators.phone_number import validate_phone_number
from utils.serializers.address import AddressDefaultFieldMixin

from stores.serializers.store import StoreSerializer
from addresses.models.store_address import StoreAddress
from addresses.serializers.common import StateListSerializer, CountryViewSerializer


class StoreAddressNestedViewSerializer(serializers.ModelSerializer):
    state = StateListSerializer(source='state_id')
    country = CountryViewSerializer(source='country_id')

    class Meta:
        model = StoreAddress
        fields = ('id', 'street1', 'street2', 'city', 'state', 'country', 'label', 'number', 'zip_code')


class StoreAddressPublicViewSerializer(serializers.ModelSerializer):
    state = StateListSerializer(source='state_id')
    country = CountryViewSerializer(source='country_id')

    class Meta:
        model = StoreAddress
        fields = ('id', 'street1', 'street2', 'city', 'state', 'country', 'label', 'number', 'zip_code')


class StoreAddressViewSerializer(serializers.ModelSerializer):
    state = StateListSerializer(source='state_id')
    country = CountryViewSerializer(source='country_id')
    store = StoreSerializer(source='store_id')

    class Meta:
        model = StoreAddress
        fields = ( 'id', 'street1', 'street2', 'city', 'state', 'country', 'label', 'number', 'zip_code', 'is_default',
                   'is_active', 'store', 'created_by', 'updated_by', 'created_on', 'updated_on')


class StoreAddressListSerializer(serializers.ModelSerializer):
    state = StateListSerializer(source='state_id')
    country = CountryViewSerializer(source='country_id')
    store = StoreSerializer(source='store_id')

    class Meta:
        model = StoreAddress
        fields = ('id', 'street1', 'street2', 'city', 'state', 'country', 'label', 'number', 'zip_code', 'is_default',
                  'is_active', 'store', 'created_by', 'updated_by', 'created_on', 'updated_on')


class StoreAddressCreateUpdateSerializer(AddressDefaultFieldMixin, serializers.ModelSerializer):
    class Meta:
        model = StoreAddress
        fields = "__all__"
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

        if self.context['request'].method == "POST":
            if "store_id" not in attrs:
                errors.setdefault("store_id", []).append(REQUIRED_FIELD)

            if "number" not in attrs:
                errors.setdefault("number", []).append(REQUIRED_FIELD)

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
        filter_kwargs = {'store_id': validated_data['store_id'].id, 'is_default': True}

        # validate store default address
        validated_data = self._check_default_address_exits(StoreAddress, validated_data, filter_kwargs)

        # add new address
        instance = StoreAddress.objects.create(**validated_data)
        return instance

    def update(self, instance, validated_data):
        validated_data['updated_by'] = self.context['request'].user

        # filter address query
        filter_kwargs = {'store_id': instance.store_id.id, 'is_default': True}

        # validate store default address
        validated_data = self._check_default_address_exits(StoreAddress, validated_data, filter_kwargs)

        # setter to set instance value
        for key, item in validated_data.items():
            setattr(instance, key, item)

        instance.updated_on = timezone.now()

        # saved updated store address value
        instance.save()

        return instance

    @staticmethod
    def _remove_staff_permission(removeStaffPermissionList, user_obj):
        # get permission code
        del_permissions = Permission.objects.filter(codename__in=removeStaffPermissionList)

        # removed permission to the staff
        user_obj.user_permissions.remove(*del_permissions)

    @staticmethod
    def _get_all_location_permission(user_obj, store_id, location_id):
        from users.models.custom_permission import CustomPermission
        existWorkOrderPerm = []
        existSalesOrderPerm = []

        # get all location permission
        customPermissionListObj = CustomPermission.objects.filter(~Q(location_id__in=[location_id]),
                                                                  user_id=user_obj.id,
                                                                  store_id=store_id,
                                                                  is_active=True)
        for xx in customPermissionListObj:
            modulePermissionListObj = xx.module_permission.filter(is_active=True)

            for modulePermissionObj in modulePermissionListObj:
                if modulePermissionObj.module_id == 5:
                    existSalesOrderPerm.extend(modulePermissionObj.permissions)
                elif modulePermissionObj.module_id == 6:
                    existWorkOrderPerm.extend(modulePermissionObj.permissions)

        return existSalesOrderPerm, existWorkOrderPerm

    def _remove_staff_location_permission(self, removeStaffLocationPermissions, user_obj, store_id, location_id):
        # get all allotted location permission for sales order and work order
        existSalesOrderPerm, existWorkOrderPerm = self._get_all_location_permission(user_obj, store_id, location_id)
        staff_perm_dict = mapped_staff_group_django_permission_json
        removeStaffPermissionList = []

        for permObj in removeStaffLocationPermissions:
            if permObj['module_id'] not in [5, 6]:
                continue

            for perKey in permObj['permissions']:
                if permObj['module_id'] == 5 and perKey in existSalesOrderPerm or \
                        permObj['module_id'] == 6 and perKey in existWorkOrderPerm:
                    continue

                # get all perm meta keys
                permKeys = list(staff_perm_dict[permObj['module_id']]['permissions'].keys())

                if perKey in permKeys:
                    # get perm meta key object
                    permMetaKeyList = staff_perm_dict[permObj['module_id']]['permissions'][perKey]

                    for permMetaKey in permMetaKeyList:
                        if permMetaKey not in removeStaffPermissionList:
                            removeStaffPermissionList.append(permMetaKey)

        if removeStaffPermissionList:
            self._remove_staff_permission(removeStaffPermissionList, user_obj)

    def delete_address(self, instance, user_obj):
        if instance.is_default:
            # get all store Address
            address_list_obj = StoreAddress.objects.filter(store_id=instance.store_id.id, is_active=True,
                                                           is_default=False).first()

            # set is default true other store Address
            if address_list_obj:
                address_list_obj.is_default = True
                address_list_obj.updated_by = user_obj
                address_list_obj.updated_on = timezone.now()
                address_list_obj.save()

        instance.is_active = False
        instance.is_default = False
        instance.updated_by = user_obj
        instance.updated_on = timezone.now()
        instance.save()

        # update permission
        customPermissionListObj = instance.custom_permission.filter(is_active=True)

        delStaffAddressPerms = {}

        # clean data and group by user object
        for xxx in customPermissionListObj:
            if xxx.user_id.id not in delStaffAddressPerms:
                delStaffAddressPerms[xxx.user_id.id] = [xxx]
            else:
                delStaffAddressPerms[xxx.user_id.id].append(xxx)

        for delUserPremId, permListObj in delStaffAddressPerms.items():
            removeStaffLocationPermissions = []

            for customPreObj in permListObj:

                # get all custom module location permission
                customModulePreListObj = customPreObj.module_permission.filter(is_active=True)

                for customModulePreObj in customModulePreListObj:
                    customModulePreObj.is_active = False
                    customModulePreObj.updated_by = user_obj
                    customModulePreObj.updated_on = timezone.now()
                    customModulePreObj.save()

                    del_permission = dict(module_id=customModulePreObj.module_id,
                                          permissions=customModulePreObj.permissions)
                    removeStaffLocationPermissions.append(del_permission)

                customPreObj.is_active = False
                customPreObj.updated_by = user_obj
                customPreObj.updated_on = timezone.now()
                customPreObj.save()

            if removeStaffLocationPermissions:
                self._remove_staff_location_permission(removeStaffLocationPermissions, user_obj, instance.store_id.id,
                                                  instance.id)