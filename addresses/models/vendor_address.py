from django.utils import timezone
from django.contrib import admin
from django.db import models
from django.utils.translation import ugettext_lazy as _

from activity_logs.models.manager import ActivityLogManager
from vendors.models.vendor import Vendor
from addresses.models.base import BaseAddress


class VendorAddress(BaseAddress):
    label = models.CharField(_("Label"), max_length=60, blank=True)
    phone_number = models.CharField(_("Phone Number"), max_length=20, blank=True)
    vendor_id = models.ForeignKey(Vendor, on_delete=models.CASCADE, null=True, blank=True, db_column='vendor_id',
                                  related_name="address")
    _activity_meta = ActivityLogManager()

    class Meta:
        db_table = 'vendor_addresses'

    def __str__(self):
        return self.street1

    def delete_address(self, user):
        if self.is_default:
            # get all vendor Address
            address_list_obj = VendorAddress.objects.filter(vendor_id=self.vendor_id.id, is_active=True,
                                                            is_default=False).first()

            # set is default true other vendor Address
            if address_list_obj:
                address_list_obj.is_default = True
                address_list_obj.updated_by = user
                address_list_obj.updated_on = timezone.now()
                address_list_obj.save()

        self.is_active = False
        self.is_default = False
        self.updated_by = user
        self.updated_on = timezone.now()
        self.save()


class VendorAddressAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return self.model.objects.filter(vendor_id__isnull=False)
