from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings


class Country(models.Model):
    code = models.CharField(_("Code"), max_length=32)
    name = models.CharField(_("Name"), max_length=120)

    objects = models.Manager()

    class Meta:
        db_table = 'countries'

    def __str__(self):
        return self.name


class State(models.Model):
    code = models.CharField(_("Code"), max_length=32)
    name = models.CharField(_("Name"), max_length=120)
    country_id = models.ForeignKey(Country, on_delete=models.CASCADE, db_column='country_id')

    objects = models.Manager()

    class Meta:
        db_table = 'states'

    def __str__(self):
        return self.name


class City(models.Model):
    code = models.CharField(_("Code"), max_length=62)
    name = models.CharField(_("Name"), max_length=120)
    state_id = models.ForeignKey(State, on_delete=models.CASCADE, db_column='state_id')

    objects = models.Manager()

    class Meta:
        db_table = 'cities'

    def __str__(self):
        return self.name


class BaseAddress(models.Model):
    street1 = models.CharField(_("Street1"), max_length=255)
    street2 = models.CharField(_("Street2"), max_length=255, blank=True)
    city = models.CharField("City", max_length=250)
    state_id = models.ForeignKey(State, on_delete=models.PROTECT, db_column='state_id')
    country_id = models.ForeignKey(Country, on_delete=models.PROTECT, db_column='country_id')
    zip_code = models.CharField(_("Zip Code"), max_length=8)
    is_default = models.BooleanField(_("Is Default"), default=False)
    is_active = models.BooleanField(_("Is Active"), default=True)
    latitude = models.CharField(_("Latitude"), max_length=60, blank=True)
    longitude = models.CharField(_("Longitude"), max_length=60, blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField("Updated On", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.PROTECT, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.PROTECT, related_name="+")

    objects = models.Manager()

    class Meta:
        abstract = True