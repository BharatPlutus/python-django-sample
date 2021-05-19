from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone

from activity_logs.models.manager import ActivityLogManager
from vendors.models.vendor import Vendor


class CustomService(models.Model):
    name = models.CharField("Name", max_length=120)
    price = models.DecimalField("Price", max_digits=20, decimal_places=2,
                                validators=[MinValueValidator(Decimal('0.00'))])
    description = models.TextField("Description", null=True, blank=True)
    short_description = models.CharField("Short Description", max_length=500)
    is_active = models.BooleanField("Is Active", default=True)
    vendor_id = models.ForeignKey(Vendor, on_delete=models.CASCADE, db_column='vendor_id', related_name="services")

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField("Updated On", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.PROTECT, related_name='+')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.PROTECT, related_name='+')

    objects = models.Manager()
    _activity_meta = ActivityLogManager()

    class Meta:
        db_table = 'custom_services'

        # add custom permission
        permissions = [('list_customservice', 'Can list custom service')]

    def __str__(self):
        return "{0}".format(self.name)

    def delete(self, using=None, keep_parents=False):
        self.is_active = False
        self.updated_on = timezone.now()
        self.save()