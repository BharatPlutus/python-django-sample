from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone

from activity_logs.models.manager import ActivityLogManager
from common_config.models.category import Category
from common_config.models.image import Image
from addresses.models.admin_address import AdminAddress
from stores.models.store import Store


class Service(models.Model):
    STATUS_CHOICES = (
        (1, "Draft"),
        (2, "Enabled"),
        (3, "Disabled"),
    )

    name = models.CharField("Name", max_length=120)
    category_tags = models.ManyToManyField(Category, blank=True, related_name='category_tags')
    item_tags = models.ManyToManyField(Category, blank=True, related_name='item_tags')
    price = models.DecimalField("Price", max_digits=20, decimal_places=2,
                                validators=[MinValueValidator(Decimal('0.00'))])
    description = models.TextField("Description", null=True, blank=True)
    sort_description = models.CharField("Sort Description", blank=True, max_length=500)
    images = models.ManyToManyField(Image, blank=True, related_name='service_images')
    store_id = models.ForeignKey(Store, null=True, blank=True, on_delete=models.CASCADE, db_column='store_id')
    address_id = models.ForeignKey(AdminAddress, on_delete=models.PROTECT, db_column='address_id', null=True, blank=True)
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=1)
    is_default = models.BooleanField("Is Default", default=False)
    is_active = models.BooleanField("Is Active", default=True)
    sku = models.CharField("SKU", max_length=120, blank=True)
    is_backend = models.BooleanField("Is Backend", default=False)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField("Updated On", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.PROTECT, related_name='+')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.PROTECT, related_name='+')

    objects = models.Manager()
    _activity_meta = ActivityLogManager()

    class Meta:
        db_table = 'services'

        # add custom permission
        permissions = [('list_service', 'Can list service')]

    def __str__(self):
        return "{0}".format(self.name)

    def delete(self, using=None, keep_parents=False):
        self.is_active = False
        self.updated_on = timezone.now()
        self.save()

        # update price group service
        for service_obj in self.price_group_services.all():
            service_obj.is_active = False
            service_obj.updated_on = timezone.now()
            service_obj.save()