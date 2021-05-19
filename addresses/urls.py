from django.urls import path

from addresses.views.admin_address import AdminAddressesRetrieveUpdateDeleteView, AdminAddressesListCreateView
from addresses.views.store_address import StoreAddressesListCreateView, StoreAddressesRetrieveUpdateDeleteView, \
    StoreStaffUserAllowLocationListView, StoreLocationListView
from addresses.views.common import CountryListView, StateListView, CityListView, FilterCityListView
from addresses.views.customer_address import CustomerAddressesListCreateView, \
    CustomerAddressesRetrieveUpdateDeleteView
from addresses.views.vendor_address import VendorAddressesListCreateView, VendorAddressesRetrieveUpdateDeleteView

urlpatterns = [

    path('api/v1/countries', CountryListView.as_view(), name='list_country'),
    path('api/v1/countries/<int:country_id>/states', StateListView.as_view(), name='list_state'),
    path('api/v1/states/<int:state_id>/cities', CityListView.as_view(), name='list_cities'),
    path('api/v1/cities', FilterCityListView.as_view(), name='filter_city_list'),

    # store address
    path('api/v1/store-addresses', StoreAddressesListCreateView.as_view(), name='store_addresses'),
    path('api/v1/store-addresses/<int:pk>', StoreAddressesRetrieveUpdateDeleteView.as_view(),
         name='details_store_addresses'),

    # filter store addresses by user permission
    path('api/v1/store/<int:pk>/staff-locations', StoreStaffUserAllowLocationListView.as_view(),
         name='allow_staff_store_location'),
    path('api/v1/store/<int:pk>/locations', StoreLocationListView.as_view(),
         name='store_location'),

    # vendor address
    path('api/v1/vendor-addresses', VendorAddressesListCreateView.as_view(), name='vendor_addresses'),
    path('api/v1/vendor-addresses/<int:pk>', VendorAddressesRetrieveUpdateDeleteView.as_view(),
         name='details_vendor_addresses'),

    # customer address
    path('api/v1/customer-addresses', CustomerAddressesListCreateView.as_view(), name='customer_addresses'),
    path('api/v1/customer-addresses/<int:pk>', CustomerAddressesRetrieveUpdateDeleteView.as_view(),
         name='details_customer_addresses'),

    # super admin address
    path('api/v1/addresses', AdminAddressesListCreateView.as_view(), name='addresses'),
    path('api/v1/addresses/<int:pk>', AdminAddressesRetrieveUpdateDeleteView.as_view(),
         name='details_addresses'),
]
