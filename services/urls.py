from django.urls import path
from services.views.service import ServiceListCreateView, ServiceRetrieveUpdateDeleteView, \
    UpdateServiceOptionSequenceNumber
from services.views.service_option import ServiceOptionDestroyView, ServiceOptionLogicDestroyView, \
    ServiceOptionImageDestroyView
from services.views.search_service import CustomerPortalServiceView, CustomerPortalServiceDetailView
from services.views.custom_service import CustomServiceListCreateView, CustomServiceRetrieveUpdateDeleteView
from services.views.store_service import StoreServiceListView, StoreApproveVendorServicePriceView, \
    StoreDeclineVendorServicePriceView

urlpatterns = [

    path('api/v1/services', ServiceListCreateView.as_view(), name='service'),
    path('api/v1/services/<int:pk>', ServiceRetrieveUpdateDeleteView.as_view(), name='details_service'),
    path('api/v1/services/<int:service_id>/service-options/<int:pk>', ServiceOptionDestroyView.as_view(),
         name='details_service_option'),

    path('api/v1/services/<int:service_id>/service-option-logic/<int:pk>', ServiceOptionLogicDestroyView.as_view(),
         name='delete_service_option_logic'),
    path('api/v1/services/<int:service_id>/service-option/<int:pk>/images/<int:image_id>',
         ServiceOptionImageDestroyView.as_view(), name='delete_service_option_image'),

    # portal services
    path('api/v1/stores/<int:pk>/portal-services', CustomerPortalServiceView.as_view(), name='search_service'),
    path('api/v1/stores/<int:store_id>/portal-services/<int:pk>', CustomerPortalServiceDetailView.as_view(),
         name='get_single_store_service'),

    # custom services
    path('api/v1/custom/services', CustomServiceListCreateView.as_view(), name='custom_service'),
    path('api/v1/custom/<int:vendor_id>/services/<int:pk>', CustomServiceRetrieveUpdateDeleteView.as_view(),
         name='detail_custom_service'),

]
