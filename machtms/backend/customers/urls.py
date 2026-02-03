from rest_framework.routers import SimpleRouter
from machtms.backend.customers.views import (
    CustomerViewSet,
    CustomerAPViewSet,
    CustomerRepresentativeViewSet,
)

router = SimpleRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'customer-aps', CustomerAPViewSet, basename='customer-ap')
router.register(r'customer-representatives', CustomerRepresentativeViewSet, basename='customer-representative')

urlpatterns = router.urls
