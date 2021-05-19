from django.utils import timezone
from django.contrib import admin
from addresses.models.store_address import StoreAddress


class AdminAddress(StoreAddress):
    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.store_id = None
        super(AdminAddress, self).save(*args, **kwargs)

    def delete_address(self, user):
        if self.is_default:
            # get all admin Address
            address_list_obj = AdminAddress.objects.filter(created_by=self.created_by.id, is_active=True,
                                                           is_default=False).first()

            # set is default true other admin Address
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


class AdminAddressAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return self.model.objects.filter(store_id__isnull=True)
