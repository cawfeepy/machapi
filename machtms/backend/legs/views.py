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
    ShipmentAssignmentModifySerializer,
    ShipmentAssignmentModifyResponseSerializer,
)


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
        request=ShipmentAssignmentModifySerializer,
        responses={200: ShipmentAssignmentModifyResponseSerializer},
    )
    @action(detail=False, methods=['post'], url_path='modify')
    def modify(self, request):
        """
        Bulk modify shipment assignments.

        Supports three operations:
        - Swap: Provide both to_delete (2 items) and to_add (2 items)
        - Unassign: Provide only to_delete with empty to_add
        - Assign: Provide only to_add with empty to_delete
        """
        serializer = ShipmentAssignmentModifySerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        to_delete_instances = serializer.validated_data.get('to_delete', [])
        to_add_data = serializer.validated_data.get('to_add', [])

        deleted_ids = [instance.id for instance in to_delete_instances]

        with transaction.atomic():
            deleted_count = len(to_delete_instances)
            if to_delete_instances:
                ShipmentAssignment.objects.filter(id__in=deleted_ids).delete()

            created_instances = []
            for item in to_add_data:
                instance = ShipmentAssignment.objects.create(**item)
                created_instances.append(instance)

        return Response({
            'deleted_count': deleted_count,
            'deleted_ids': deleted_ids,
            'created_count': len(created_instances),
            'created': ShipmentAssignmentSerializer(created_instances, many=True).data,
        })
