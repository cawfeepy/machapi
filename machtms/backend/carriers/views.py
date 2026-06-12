from rest_framework import filters, viewsets
from machtms.core.base.mixins import TMSViewMixin
from machtms.backend.carriers.models import Carrier, Driver
from machtms.backend.carriers.serializers import (
    CarrierSerializer,
    CarrierListSerializer,
    DriverSerializer,
    DriverListSerializer,
)


class CarrierViewSet(TMSViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for Carrier model.
    Provides CRUD operations for carriers.
    """
    queryset = Carrier.objects.all()
    serializer_class = CarrierSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['^carrier_name']

    def get_serializer_class(self):
        if self.action == 'list':
            return CarrierListSerializer
        return CarrierSerializer


class DriverViewSet(TMSViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for Driver model.
    Provides CRUD operations for drivers.
    """
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['^first_name', '^last_name']

    def get_serializer_class(self):
        if self.action == 'list':
            return DriverListSerializer
        return DriverSerializer
