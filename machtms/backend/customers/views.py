from rest_framework import viewsets
from machtms.core.base.mixins import TMSViewMixin
from machtms.backend.customers.models import Customer, CustomerAP, CustomerRepresentative
from machtms.backend.customers.serializers import (
    CustomerSerializer,
    CustomerListSerializer,
    CustomerAPSerializer,
    CustomerRepresentativeSerializer,
)


class CustomerViewSet(TMSViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for Customer model.
    Provides CRUD operations for customers.
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    def get_serializer_class(self):
        if self.action == 'list':
            return CustomerListSerializer
        return CustomerSerializer


class CustomerAPViewSet(TMSViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for CustomerAP model.
    Provides CRUD operations for customer AP contacts.
    """
    queryset = CustomerAP.objects.all()
    serializer_class = CustomerAPSerializer


class CustomerRepresentativeViewSet(TMSViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for CustomerRepresentative model.
    Provides CRUD operations for customer representatives.
    """
    queryset = CustomerRepresentative.objects.all()
    serializer_class = CustomerRepresentativeSerializer
