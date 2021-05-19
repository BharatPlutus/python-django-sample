from django.contrib import admin
from django.db import models
from django.utils.translation import ugettext_lazy as _

from activity_logs.models.manager import ActivityLogManager
from stores.models.store import Store
from addresses.models.base import BaseAddress


class StoreAddress(BaseAddress):
    number = models.CharField(_("Number"), max_length=20, blank=True)
    label = models.CharField(_("Label"), max_length=60, blank=True)
    store_id = models.ForeignKey(Store, on_delete=models.CASCADE, null=True, blank=True, db_column='store_id',
                                 related_name="address")
    _activity_meta = ActivityLogManager()

    class Meta:
        db_table = 'store_addresses'

        permissions = [('view_store_location', 'Can view list of store location')]

    def __str__(self):
        return self.street1


class StoreAddressAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return self.model.objects.filter(store_id__isnull=False)
