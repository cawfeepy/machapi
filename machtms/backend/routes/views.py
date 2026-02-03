from rest_framework import viewsets, filters, permissions

from machtms.core.base.mixins import TMSViewMixin
from machtms.backend.routes.models import Stop
from machtms.backend.routes.serializers import StopSerializer


class StopViewSet(TMSViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing stops in transportation routes.

    Provides full CRUD operations for Stop objects.
    Supports searching by address, PO numbers, and stop number.
    Results are ordered by start_range by default.
    """

    queryset = Stop.objects.all()
    serializer_class = StopSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'address__street',
        'address__city',
        'address__state',
        'address__zipcode',
        'po_numbers',
        'stop_number',
    ]
    ordering_fields = ['start_range', 'end_range', 'timestamp', 'action']
    ordering = ['start_range']
