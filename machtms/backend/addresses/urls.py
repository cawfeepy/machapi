from rest_framework import routers
from machtms.backend.addresses.views import (
    AddressViewSet,
    AddressUsageAccumulateViewSet,
    AddressUsageByCustomerAccumulateViewSet,
    CustomerAddressViewSet,
    CarrierAddressViewSet,
)

router = routers.SimpleRouter()
router.register(r'addresses', AddressViewSet, basename='address')
router.register(r'customer-addresses', CustomerAddressViewSet, basename='customer-address')
router.register(r'carrier-addresses', CarrierAddressViewSet, basename='carrier-address')
router.register(r'address-usage-accumulate', AddressUsageAccumulateViewSet, basename='address-usage-accumulate')
router.register(r'address-usage-by-customer-accumulate', AddressUsageByCustomerAccumulateViewSet, basename='address-usage-by-customer-accumulate')

urlpatterns = router.urls
