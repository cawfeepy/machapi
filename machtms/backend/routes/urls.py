from rest_framework.routers import SimpleRouter

from machtms.backend.routes.views import StopViewSet


router = SimpleRouter()
router.register(r'stops', StopViewSet, basename='stop')

urlpatterns = router.urls
