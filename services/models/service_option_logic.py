from django.db import models
from activity_logs.models.manager import ActivityLogManager
from services.models.service_option import ServiceOption


class ServiceOptionAction(models.Model):
    ACTION_CHOICES = (
        ('show', "show"),
        ('hide', "hide")
    )

    CONDITIONAL_CHOICES = (
        ('all', "and"),
        ('one', "or"),
        ('none', "and")
    )

    apply_to_option_id = models.ForeignKey(ServiceOption, on_delete=models.CASCADE, db_column='apply_to_option_id',
                                           related_name="option_logic")
    action = models.CharField("Action", max_length=4, choices=ACTION_CHOICES)
    conditional_join = models.CharField("Conditional Join", max_length=4, choices=CONDITIONAL_CHOICES)
    conditional_logic = models.CharField("Conditional Logic", max_length=500, blank=True)

    objects = models.Manager()
    _activity_meta = ActivityLogManager()

    class Meta:
        db_table = 'service_option_action'


class ServiceOptionRule(models.Model):
    OPERATOR_TYPE_CHOICES = (
        ('=', "="),
        ('contains', "contains"),
        ('>=', ">="),
        ('<=', "<="),
        ('<', "<"),
        ('>', ">"),
        ('!=', "!=")
    )

    option_action_id = models.ForeignKey(ServiceOptionAction, on_delete=models.CASCADE, db_column='option_action_id',
                                         related_name="rules")
    compare_option_field = models.ForeignKey(ServiceOption, on_delete=models.CASCADE, db_column='compare_option_field',
                                             related_name="option_rule")
    operator_type = models.CharField("Operator Type", max_length=8, choices=OPERATOR_TYPE_CHOICES)
    compare_to = models.CharField("Compare To", max_length=500)

    objects = models.Manager()
    _activity_meta = ActivityLogManager()

    class Meta:
        db_table = 'service_option_rule'