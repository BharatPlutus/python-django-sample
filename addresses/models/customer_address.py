from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from activity_logs.models.manager import ActivityLogManager
from stores.models.store import Store
from addresses.models.base import BaseAddress
from customers.models.customer import Customer


class CustomerAddress(BaseAddress):
    ADDRESS_TYPE_CHOICES = (
        ('b', "Business"),
        ('r', "Residential"),
    )

    first_name = models.CharField(_("First Name"), max_length=120)
    last_name = models.CharField(_("Last Name"), max_length=120)
    phone_number = models.CharField(_("Phone Number"), max_length=20, blank=True)
    address_type = models.CharField(_("Address Type"), max_length=1, choices=ADDRESS_TYPE_CHOICES)
    store_id = models.ForeignKey(Store, on_delete=models.CASCADE, db_column='store_id')
    customer_id = models.ForeignKey(Customer, on_delete=models.CASCADE, db_column='customer_id',
                                    related_name="addresses")
    is_billing_address = models.BooleanField("Is Billing Address", default=False)

    _activity_meta = ActivityLogManager()

    class Meta:
        db_table = 'customer_addresses'

    def __str__(self):
        return self.street1

    def delete_address(self, user):
        if self.is_default:
            # get all customer Address
            address_list_obj = CustomerAddress.objects.filter(customer_id=self.customer_id.id, is_active=True,
                                                              is_default=False).first()

            # set is default True other customer Address
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