from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from machtms.core.base.mixins import TMSViewMixin
from machtms.backend.legs.models import Leg, ShipmentAssignment
from machtms.backend.legs.serializers import (
    LegSerializer,
    ShipmentAssignmentSerializer,
    ShipmentAssignmentSwapSerializer,
    ShipmentAssignmentSwapResponseSerializer,
    ShipmentAssignmentBulkDeleteSerializer,
    ShipmentAssignmentBulkDeleteResponseSerializer,
)
from machtms.backend.legs.utils import swap_shipment_assignments


class LegViewSet(TMSViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for viewing and editing Leg instances.

    Provides standard CRUD operations for legs.
    """
    queryset = Leg.objects.all()
    serializer_class = LegSerializer


class ShipmentAssignmentViewSet(TMSViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for viewing and editing ShipmentAssignment instances.

    Provides standard CRUD operations for shipment assignments,
    plus a bulk modify action for driver swaps and unassigns.
    """
    queryset = ShipmentAssignment.objects.all()
    serializer_class = ShipmentAssignmentSerializer


    @extend_schema(
        request=ShipmentAssignmentSwapSerializer,
        responses={200: ShipmentAssignmentSwapResponseSerializer},
    )
    @action(detail=False, methods=['post'], url_path='swap')
    def swap(self, request):
        """
        Swap drivers between two shipment assignments.

        Expects: {swap: [{'leg_id': 1, 'driver_id': 2}, {'leg_id': 3, 'driver_id': 4}]}
        """
        serializer = ShipmentAssignmentSwapSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        swap_data = [
            {'leg_id': item['leg_id'].id, 'driver_id': item['driver_id'].id}
            for item in serializer.validated_data['swap']
        ]

        result = swap_shipment_assignments(swap_data, request.organization)

        return Response({
            'deleted_count': result['deleted_count'],
            'deleted_ids': result['deleted_ids'],
            'created_count': result['created_count'],
            'created': ShipmentAssignmentSerializer(result['created'], many=True).data,
        })

    @extend_schema(
        request=ShipmentAssignmentBulkDeleteSerializer,
        responses={200: ShipmentAssignmentBulkDeleteResponseSerializer},
    )
    @action(detail=False, methods=['post'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """
        Bulk delete shipment assignments.

        Expects: {ids: [1, 2, 3]}
        """
        serializer = ShipmentAssignmentBulkDeleteSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        assignments_to_delete = serializer.validated_data['ids']
        deleted_ids = [a.id for a in assignments_to_delete]

        ShipmentAssignment.objects.filter(id__in=deleted_ids).delete()

        return Response({
            'deleted_count': len(deleted_ids),
            'deleted_ids': deleted_ids,
        })
