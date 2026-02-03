from django.core.exceptions import ValidationError
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer
from machtms.backend.routes.serializers import StopSerializer
from machtms.core.base.serializers import (
    TMSBaseSerializer,
    RelatedFieldAlternative,
    FlexiblePrimaryKeyRelatedField,
)
from machtms.core.base.mixins import AutoNestedMixin, NestedRelationConfig
from machtms.backend.legs.models import Leg, ShipmentAssignment
from machtms.backend.carriers.models import Carrier, Driver
from machtms.backend.carriers.serializers import CarrierSerializer, DriverSerializer
from machtms.backend.legs.openapi_doc import LEG_EXAMPLES, SHIPMENT_ASSIGNMENT_MODIFY_EXAMPLES


class ShipmentAssignmentNestedSerializer(TMSBaseSerializer):
    """
    Lightweight serializer for nested shipment assignments within LegSerializer.

    Accepts only carrier and driver as primary keys. The leg field is
    automatically set by the AutoNestedMixin when creating/updating.

    Uses FlexiblePrimaryKeyRelatedField to accept both PKs and model instances.
    This allows the serializer to be re-validated after the parent serializer
    has already converted PKs to instances during nested updates.
    """
    id = serializers.IntegerField(required=False)
    carrier = FlexiblePrimaryKeyRelatedField(queryset=Carrier.objects.all())
    driver = FlexiblePrimaryKeyRelatedField(queryset=Driver.objects.all())

    class Meta(TMSBaseSerializer.Meta):
        model = ShipmentAssignment
        fields = TMSBaseSerializer.Meta.fields + ['id', 'carrier', 'driver']

    def validate(self, attrs):
        carrier = attrs.get('carrier')
        driver = attrs.get('driver')
        if carrier and driver and driver.carrier_id != carrier.pk:
            raise serializers.ValidationError({
                'driver': 'Driver does not belong to the specified carrier.'
            })
        return attrs


@extend_schema_serializer(examples=LEG_EXAMPLES)
class LegSerializer(AutoNestedMixin, TMSBaseSerializer):
    id = serializers.IntegerField(required=False)
    load = serializers.PrimaryKeyRelatedField(read_only=True)
    stops = StopSerializer(many=True, required=False)
    shipment_assignments = ShipmentAssignmentNestedSerializer(many=True, required=False)

    class Meta:
        model = Leg
        fields = ["id", "load", "stops", "shipment_assignments"]

    INVALID_TRANSITIONS = {
        "LL": {"LL", "HL", "EMPP", "EMPD", "HUBP"},
        "HL": {"LL", "HL", "EMPP", "EMPD", "HUBP"},
        "LU": {"LU", "LD", "HL", "HUBP"},
        "EMPP": {"EMPP", "LU", "LD", "HL", "HUBP"},
        "LD": {"LL", "LU", "LD", "EMPD", "HUBD", "TW"},
        "EMPD": {"LL", "LU", "LD", "EMPD", "HUBD", "TW"},
        "HUBD": {"LL", "LU", "LD", "EMPD", "HUBD", "TW"},
        "HUBP": {"HUBP", "EMPP", "HL"},
    }

    nested_relations = {
        'stops': NestedRelationConfig(
            parent_field_name='leg',
            related_manager_name='stops',
            serializer_class=StopSerializer,
        ),
        'shipment_assignments': NestedRelationConfig(
            parent_field_name='leg',
            related_manager_name='shipment_assignments',
            serializer_class=ShipmentAssignmentNestedSerializer,
        )
    }

    def validate(self, attrs):
        stops_data = attrs.get("stops") or []

        for i in range(1, len(stops_data)):
            prev_action = stops_data[i - 1].get("action")
            curr_action = stops_data[i].get("action")
            invalid_next = self.INVALID_TRANSITIONS.get(prev_action, set())
            if curr_action in invalid_next:
                raise ValidationError(
                    {"stops": f"Action {curr_action} cannot follow {prev_action} at index {i}."}
                )

        return attrs


class ShipmentAssignmentSerializer(TMSBaseSerializer):
    """
    Serializer for the ShipmentAssignment model.

    Accepts primary keys for carrier, driver, and leg on input.
    Returns full nested JSON for carrier and driver on output.
    """
    carrier = RelatedFieldAlternative(
        queryset=Carrier.objects.all(),
        serializer=CarrierSerializer
    )
    driver = RelatedFieldAlternative(
        queryset=Driver.objects.all(),
        serializer=DriverSerializer
    )
    leg = RelatedFieldAlternative(
            queryset=Leg.objects.all(),
            write_only=True)

    class Meta(TMSBaseSerializer.Meta):
        model = ShipmentAssignment
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'carrier',
            'driver',
            'leg',
        ]
        read_only_fields = ['id']


class ShipmentAssignmentCreateItemSerializer(TMSBaseSerializer):
    """
    Serializer for items in the to_add array of the modify endpoint.

    Uses TMSBaseSerializer to auto-attach organization on create.
    Accepts primary keys for carrier, driver, and leg.
    """
    carrier = serializers.PrimaryKeyRelatedField(queryset=Carrier.objects.all())
    driver = serializers.PrimaryKeyRelatedField(queryset=Driver.objects.all())
    leg = serializers.PrimaryKeyRelatedField(queryset=Leg.objects.all())

    class Meta(TMSBaseSerializer.Meta):
        model = ShipmentAssignment
        fields = TMSBaseSerializer.Meta.fields + ['carrier', 'driver', 'leg']


@extend_schema_serializer(examples=SHIPMENT_ASSIGNMENT_MODIFY_EXAMPLES)
class ShipmentAssignmentModifySerializer(serializers.Serializer):
    """
    Serializer for bulk modify operations on ShipmentAssignments.

    Supports three operations:
    - Swap: Provide both to_delete (2 items) and to_add (2 items)
    - Unassign: Provide only to_delete with empty to_add
    - Assign: Provide only to_add with empty to_delete
    """
    to_delete = serializers.PrimaryKeyRelatedField(
        queryset=ShipmentAssignment.objects.all(),
        many=True,
        required=False,
    )
    to_add = ShipmentAssignmentCreateItemSerializer(many=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'organization'):
            self.fields['to_delete'].child_relation.queryset = (
                ShipmentAssignment.objects.fbo(organization=request.organization)
            )

    def validate(self, attrs):
        to_delete = attrs.get('to_delete', [])
        to_add = attrs.get('to_add', [])

        if not to_delete and not to_add:
            raise serializers.ValidationError(
                'At least one of to_delete or to_add must be provided.'
            )

        is_swap = bool(to_delete) and bool(to_add)
        if is_swap:
            if len(to_delete) != 2:
                raise serializers.ValidationError({
                    'to_delete': 'Swap operation requires exactly 2 assignments to delete.'
                })
            if len(to_add) != 2:
                raise serializers.ValidationError({
                    'to_add': 'Swap operation requires exactly 2 new assignments.'
                })

        return attrs


class ShipmentAssignmentModifyResponseSerializer(serializers.Serializer):
    """
    Response serializer for the modify action.

    Returns counts and details of deleted and created assignments.
    """
    deleted_count = serializers.IntegerField()
    deleted_ids = serializers.ListField(child=serializers.IntegerField())
    created = ShipmentAssignmentSerializer(many=True)
    created_count = serializers.IntegerField()
