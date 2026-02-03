from rest_framework.routers import SimpleRouter
from machtms.backend.loads.views import LoadViewSet

router = SimpleRouter()
router.register(r'loads', LoadViewSet, basename='load')

urlpatterns = router.urls
