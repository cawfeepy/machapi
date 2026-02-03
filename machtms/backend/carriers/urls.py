from rest_framework.routers import SimpleRouter
from machtms.backend.carriers.views import CarrierViewSet, DriverViewSet

router = SimpleRouter()
router.register(r'carriers', CarrierViewSet, basename='carrier')
router.register(r'drivers', DriverViewSet, basename='driver')

urlpatterns = router.urls
