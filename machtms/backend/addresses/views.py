from rest_framework import filters, viewsets
from machtms.core.base.mixins import TMSViewMixin
from machtms.backend.addresses.models import (
    Address,
    AddressUsageAccumulate,
    AddressUsageByCustomerAccumulate,
)
from machtms.backend.addresses.serializers import (
    AddressSerializer,
    AddressUsageAccumulateSerializer,
    AddressUsageByCustomerAccumulateSerializer,
)


class AddressViewSet(TMSViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing Address objects.
    Provides CRUD operations for addresses in the system.
    """
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['street', 'city', 'state', 'zip_code', 'country']
    ordering_fields = ['city', 'state', 'zip_code', 'country']
    ordering = ['city', 'state']


class AddressUsageAccumulateViewSet(TMSViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing AddressUsageAccumulate objects.
    Tracks address usage accumulation over time.
    """
    queryset = AddressUsageAccumulate.objects.all()
    serializer_class = AddressUsageAccumulateSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'address__street',
        'address__city',
        'address__state',
        'address__zip_code',
    ]
    ordering_fields = ['last_used']
    ordering = ['-last_used']


class AddressUsageByCustomerAccumulateViewSet(TMSViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing AddressUsageByCustomerAccumulate objects.
    Tracks address usage by customer accumulation for analysis.
    """
    queryset = AddressUsageByCustomerAccumulate.objects.all()
    serializer_class = AddressUsageByCustomerAccumulateSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'address__street',
        'address__city',
        'address__state',
        'address__zip_code',
    ]
    ordering_fields = ['last_used']
    ordering = ['-last_used']
