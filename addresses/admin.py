from django.contrib import admin
from addresses.models.base import City, State, Country
from addresses.models.store_address import StoreAddress, StoreAddressAdmin
from addresses.models.customer_address import CustomerAddress
from addresses.models.admin_address import AdminAddress, AdminAddressAdmin
from addresses.models.vendor_address import VendorAddress, VendorAddressAdmin

admin.site.register(City)
admin.site.register(State)
admin.site.register(Country)
admin.site.register(CustomerAddress)
admin.site.register(StoreAddress, StoreAddressAdmin)
admin.site.register(VendorAddress, VendorAddressAdmin)
admin.site.register(AdminAddress, AdminAddressAdmin)