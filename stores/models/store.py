from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator

from activity_logs.models.manager import ActivityLogManager
from stores.models.commission_rule import CommissionRule
from insurances.models.insurance import Insurance


class Store(models.Model):
    STORE_ENTITY_TYPE = (
        ('individual', "Individual"),
        ('llc', "LLC"),
        ('inc', 'Inc'),
    )

    CARD_TYPE = (
        ('visa', 'Visa'),
        ('mastercard', 'Mastercard'),
        ('citibank', 'Citibank'),
        ('american_express', 'American Express '),
        ('capital_one', 'Capital One'),
        ('bank_of_america', 'Bank of America'),
        ('discover', 'Discover'),
        ('synchrony_financial', 'Synchrony Financial'),
        ('chase', 'Chase')
    )

    name = models.CharField("Name", max_length=120, unique=True)
    subdomain = models.CharField("Sub Domain", max_length=120, unique=True)
    url = models.CharField("URL", max_length=250, unique=True)
    website_url = models.CharField("Website URL", max_length=250, blank=True)
    first_name = models.CharField("First Name", max_length=60)
    last_name = models.CharField("Last Name", max_length=120)
    public_email = models.EmailField("Public Email", max_length=150)
    public_phone = models.CharField("Public Phone", max_length=20, blank=True)
    owner_email = models.EmailField("Owner Email", max_length=150)
    owner_phone = models.CharField("Owner Phone", max_length=20)
    subscription_fee = models.DecimalField("Subscription Fee", max_digits=20, decimal_places=2,
                                           db_column='subscription_fee',
                                           validators=[MinValueValidator(Decimal('0.00'))], default=0)
    commission_rule_id = models.ForeignKey(CommissionRule, null=True, blank=True, on_delete=models.PROTECT,
                                           db_column='commission_rule_id')
    store_entity_type = models.CharField("Store Entity Type", max_length=10, choices=STORE_ENTITY_TYPE
                                         ,blank=True, null=True)
    card_type = models.CharField("Card Type", max_length=25, choices=CARD_TYPE, blank=True, null=True)
    card_last_four_digits = models.PositiveIntegerField("Card Last Four Digits", validators=[MaxValueValidator(9999)]
                                                        , blank=True, null=True)
    insurance_id = models.ForeignKey(Insurance, null=True, blank=True, on_delete=models.PROTECT,
                                     db_column='insurance_id', related_name="store_insurance")
    is_active = models.BooleanField("Is Active", default=True)
    is_repair_shop = models.BooleanField("Is Repair Shop", default=False)
    is_platform_store = models.BooleanField("Is Platform Store", default=False)
    stripe_account_id = models.CharField("Stripe Customer Id", blank=True, max_length=200)
    is_complete_white_label = models.BooleanField(default=False)
    white_label_domain = models.CharField("White Label Domain", max_length=250, blank=True)
    is_onboarding_complete = models.BooleanField("Is On Boarding Comeplete", default=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField("Updated On", blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.PROTECT, related_name='+')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.PROTECT, related_name='+')

    objects = models.Manager()
    _activity_meta = ActivityLogManager()

    class Meta:
        db_table = 'stores'

        # add custom permission
        permissions = [('list_store', 'Can list store')]

    def __str__(self):
        return "{0}".format(self.name)

    def delete(self, using=None, keep_parents=False):
        self.is_active = False
        self.save()
