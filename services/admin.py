from django.contrib import admin
from services.models.service import Service
from services.models.service_option import ServiceOption
from services.models.service_option_logic import ServiceOptionAction, ServiceOptionRule
from services.models.custom_service import CustomService

admin.site.register(Service)
admin.site.register(ServiceOption)
admin.site.register(ServiceOptionAction)
admin.site.register(ServiceOptionRule)
admin.site.register(CustomService)
