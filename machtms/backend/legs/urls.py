from rest_framework.routers import SimpleRouter

from machtms.backend.legs.views import LegViewSet, ShipmentAssignmentViewSet

router = SimpleRouter()
router.register(r'legs', LegViewSet, basename='leg')
router.register(r'shipment-assignments', ShipmentAssignmentViewSet, basename='shipment-assignment')

urlpatterns = router.urls
