from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer
from machtms.core.base.serializers import TMSBaseSerializer
from machtms.core.base.mixins import AutoNestedMixin, NestedRelationConfig
from machtms.backend.loads.models import Load
from machtms.backend.legs.models import Leg, ShipmentAssignment
from machtms.backend.legs.serializers import LegSerializer
from machtms.backend.routes.models import Stop
from machtms.backend.addresses.serializers import AddressSerializer
from machtms.backend.customers.serializers import CustomerListSerializer
from machtms.backend.carriers.serializers import CarrierListSerializer, DriverListSerializer
from machtms.backend.loads.openapi_doc import LOAD_EXAMPLES, LOAD_LIST_EXAMPLES


@extend_schema_serializer(examples=LOAD_EXAMPLES)
class LoadSerializer(AutoNestedMixin, TMSBaseSerializer):
    legs = LegSerializer(many=True, required=False)

    nested_relations = {
        'legs': NestedRelationConfig(
            parent_field_name='load',
            related_manager_name='legs',
            serializer_class=LegSerializer
        )
    }

    class Meta(TMSBaseSerializer.Meta):
        model = Load
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'reference_number',
            'bol_number',
            'customer',
            'status',
            'billing_status',
            'trailer_type',
            'legs',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


@extend_schema_serializer(examples=LOAD_LIST_EXAMPLES)
class LoadListSerializer(TMSBaseSerializer):
    class Meta(TMSBaseSerializer.Meta):
        model = Load
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'invoice_id',
            'reference_number',
            'customer',
            'income',
            'status',
            'billing_status',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# Alias for PDF generation - adjust fields as needed
LoadPDFSerializer = LoadSerializer


# ============================================================================
# Daily/Calendar View Serializers
# ============================================================================

class StopDailySerializer(TMSBaseSerializer):
    """Lightweight stop serializer for daily calendar view."""
    address = AddressSerializer(read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta(TMSBaseSerializer.Meta):
        model = Stop
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'stop_number',
            'address',
            'start_range',
            'end_range',
            'action',
            'action_display',
            'po_numbers',
        ]


class ShipmentAssignmentDailySerializer(TMSBaseSerializer):
    """ShipmentAssignment with nested carrier/driver for daily calendar view."""
    carrier = CarrierListSerializer(read_only=True)
    driver = DriverListSerializer(read_only=True)

    class Meta(TMSBaseSerializer.Meta):
        model = ShipmentAssignment
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'carrier',
            'driver',
        ]


class LegDailySerializer(TMSBaseSerializer):
    """Leg serializer with stops and assignment info for daily calendar view."""
    stops = StopDailySerializer(many=True, read_only=True)
    shipment_assignments = ShipmentAssignmentDailySerializer(many=True, read_only=True)
    is_assigned = serializers.SerializerMethodField()

    class Meta(TMSBaseSerializer.Meta):
        model = Leg
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'stops',
            'shipment_assignments',
            'is_assigned',
        ]

    def get_is_assigned(self, obj):
        """Check if leg has any shipment assignments (uses prefetched data)."""
        return len(obj.shipment_assignments.all()) > 0


class LoadDailySerializer(TMSBaseSerializer):
    """Load serializer optimized for daily calendar view."""
    customer = CustomerListSerializer(read_only=True)
    legs = LegDailySerializer(many=True, read_only=True)
    has_unassigned_leg = serializers.BooleanField(read_only=True)
    first_pickup_time = serializers.DateTimeField(read_only=True)

    class Meta(TMSBaseSerializer.Meta):
        model = Load
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'reference_number',
            'bol_number',
            'customer',
            'status',
            'billing_status',
            'trailer_type',
            'legs',
            'has_unassigned_leg',
            'first_pickup_time',
            'created_at',
            'updated_at',
        ]

