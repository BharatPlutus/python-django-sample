from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.postgres.fields import JSONField

from activity_logs.models.manager import ActivityLogManager
from common_config.models.image import Image
from services.models.service import Service


class ServiceOption(models.Model):
    STATUS_CHOICES = (
        (1, "Draft"),
        (2, "Enabled"),
        (3, "Disabled"),
    )

    FIELD_TYPE_CHOICES = (
        (1, "Short Text"),
        (2, "Long Text"),
        (3, "Number"),
        (4, "Current/Desired Size"),
        (5, "Dropdown"),
        (6, "Multi Select (Radio Buttons)"),
        (7, "Checkbox (Yes/No)"),
        (8, "Image Upload"),
        (9, "Insurance"),
        (10, "Select Radio Button (Text)"),
        (11, "Select Radio Button (Image)"),
        (12, "Warranty"),
    )

    name = models.CharField("Name", max_length=120)
    is_active = models.BooleanField("Is Active", default=True)
    service_id = models.ForeignKey(Service, on_delete=models.CASCADE, db_column='service_id',
                                   related_name="options")
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=1)
    field_type = models.SmallIntegerField(choices=FIELD_TYPE_CHOICES)
    instruction = models.TextField("Instruction", blank=True)
    tool_tips = models.TextField("Tool Tips", blank=True)
    is_required = models.BooleanField("Is Required", default=False)
    other_option = models.BooleanField("Other Option", default=False)
    other_option_value = models.CharField("Other Option Value", max_length=120, blank=True)
    field_text1 = models.TextField("Field Text1", help_text='csv format')
    field_text2 = models.TextField("Field Text2", help_text='csv format', blank=True)
    images = models.ManyToManyField(Image, blank=True, related_name='option_images')
    is_metal_type = models.BooleanField("Is Metal Type", default=False)
    is_option_cost = models.BooleanField("Is Option Cost", default=False)
    sequence = models.IntegerField(default=1)
    field_date = models.DateTimeField("Field Date", null=True, blank=True)
    meta_data = JSONField(default=dict, blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField("Updated On", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.PROTECT, related_name='+')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.PROTECT, related_name='+')

    objects = models.Manager()
    _activity_meta = ActivityLogManager()

    class Meta:
        db_table = 'service_options'

        # add custom permission
        permissions = [('list_serviceoption', 'Can list service option')]

    def __str__(self):
        return "{0} - {1}".format(self.service_id.name, self.name)

    def delete(self, using=None, keep_parents=False):
        self.is_active = False
        self.updated_on = timezone.now()
        self.save()

        # update price group service option
        for option_obj in self.price_group_options.all():
            option_obj.is_active = False
            option_obj.updated_on = timezone.now()
            option_obj.save()
