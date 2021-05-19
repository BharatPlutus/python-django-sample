from django.urls import path

from stores.views.store import StoreListCreateView, StoreRetrieveUpdateDeleteView, StoreSubDomain, \
    StoreWhiteLabelDomain, StoreGetStartedView
from stores.views.commission_rule import CommissionRuleListCreateView, CommissionRuleRetrieveUpdateDeleteView
from stores.views.white_label_setting import StoreSettingRetrieveView
from stores.views.repair_step import RepairStepCreateView, RepairStepRetrieveUpdateDeleteView

urlpatterns = [

    # store
    path('api/v1/stores', StoreListCreateView.as_view(), name='stores'),
    path('api/v1/stores/<int:pk>', StoreRetrieveUpdateDeleteView.as_view(), name='details_store'),
    path('api/v1/validate-store-subdomain/<str:subdomain>', StoreSubDomain.as_view(), name='validate_store_subdomain'),

]