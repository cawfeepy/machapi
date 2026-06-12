from datetime import datetime, date, time, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    shipment_assignment = ShipmentAssignmentDailySerializer(read_only=True)
    is_assigned = serializers.SerializerMethodField()

    class Meta(TMSBaseSerializer.Meta):
        model = Leg
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'stops',
            'shipment_assignment',
            'is_assigned',
        ]

    def get_is_assigned(self, obj):
        """Check if leg has a shipment assignment."""
        return hasattr(obj, 'shipment_assignment') and obj.shipment_assignment is not None




# ============================================================================
# Flat Per-Leg Schedule Serializers
# ============================================================================

# Datetimes that sort after every real stop time, so legs without stops are
# ordered last deterministically (tie-broken by pk).
_LEG_ORDER_SENTINEL = datetime.max.replace(tzinfo=dt_timezone.utc)


def order_legs(load):
    """
    Return a load's legs in trip sequence.

    Legs are ordered by their earliest stop ``start_range`` (the temporal
    meaning of "previous"/"next" in a multi-leg trip), tie-broken by ``pk``.
    Legs with no stops sort last. Iterates the prefetched ``load.legs`` and
    ``leg.stops`` managers, so no extra queries are issued when the caller has
    prefetched them.
    """
    legs = list(load.legs.all())

    def sort_key(leg):
        earliest = leg_earliest_start(leg)
        # First element keeps None-start legs last without ever comparing a
        # datetime against None; the sentinel only breaks ties among them.
        return (earliest is None, earliest or _LEG_ORDER_SENTINEL, leg.pk)

    return sorted(legs, key=sort_key)


def leg_earliest_start(leg):
    """
    Earliest non-null stop ``start_range`` for a leg, or ``None``.

    Iterates the (prefetched) ``leg.stops`` manager, so it issues no extra
    queries when the caller has prefetched stops. Used both to order legs into
    trip sequence and to derive a leg row's chronological sort position.
    """
    starts = [stop.start_range for stop in leg.stops.all() if stop.start_range]
    return min(starts) if starts else None


def leg_in_windows(leg, windows):
    """
    True if any of the leg's own stops starts within any requested window.

    ``windows`` is the list of ``(utc_start, utc_end)`` tuples produced by
    ``LegScheduleQuerySerializer``. The bounds are inclusive on both ends to
    mirror the DB predicate ``start_range__range=(start, end)`` used to select
    candidate loads. Iterates prefetched ``leg.stops`` -> no extra queries.
    """
    return any(
        start <= stop.start_range <= end
        for stop in leg.stops.all() if stop.start_range
        for (start, end) in windows
    )


def _leg_assignment(leg):
    """Safely fetch a leg's ShipmentAssignment (OneToOne reverse) or None."""
    return getattr(leg, 'shipment_assignment', None)


def _owner_detail(leg):
    """Full owner block for a leg's own row: carrier + driver with PKs, or None."""
    assignment = _leg_assignment(leg)
    if assignment is None:
        return None
    return {
        'carrier': {
            'id': assignment.carrier_id,
            'carrier_name': assignment.carrier.carrier_name,
        },
        'driver': {
            'id': assignment.driver_id,
            'full_name': assignment.driver.full_name,
        },
    }


def _summarize_leg(leg):
    """Condensed summary of a sibling leg for previous_legs / next_legs."""
    assignment = _leg_assignment(leg)
    if assignment is not None:
        owner = f"{assignment.carrier.carrier_name} / {assignment.driver.full_name}"
    else:
        owner = "unassigned"

    stops = []
    for stop in leg.stops.all():
        address = stop.address
        label = f"{address.place_name} - {address.city}, {address.state}" if address else ""
        stops.append({
            'label': label,
            'action': stop.action,
            'action_display': stop.get_action_display(),
            'start_range': stop.start_range,
            'end_range': stop.end_range,
        })

    return {
        'leg_id': leg.id,
        'sequence_index': getattr(leg, '_seq_index', None),
        'owner': owner,
        'stops': stops,
    }


class LegScheduleQuerySerializer(serializers.Serializer):
    """
    Validate query params for the flat per-leg schedule endpoint.

    Accepts a list of ``dates`` (each ``YYYY-MM-DD``, possibly non-consecutive)
    and an IANA ``timezone``. Each date is interpreted as the full local day
    (00:00:00 - 23:59:59.999999) in that timezone and converted to a UTC
    ``(start, end)`` window. ``validated_data`` exposes ``windows`` (a list of
    UTC datetime tuples) and ``tz`` (the resolved ZoneInfo).
    """
    dates = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    timezone = serializers.CharField()

    def validate(self, attrs):
        try:
            tz = ZoneInfo(attrs['timezone'])
        except (ZoneInfoNotFoundError, KeyError, ValueError):
            raise serializers.ValidationError(
                {'timezone': f"Invalid IANA timezone: {attrs['timezone']}"}
            )

        utc = ZoneInfo('UTC')
        windows = []
        for raw_date in attrs['dates']:
            try:
                day = date.fromisoformat(raw_date)
            except ValueError:
                raise serializers.ValidationError(
                    {'dates': f'Invalid date (expected YYYY-MM-DD): {raw_date}'}
                )
            local_start = datetime.combine(day, time.min, tzinfo=tz)
            local_end = datetime.combine(day, time(23, 59, 59, 999999), tzinfo=tz)
            windows.append((local_start.astimezone(utc), local_end.astimezone(utc)))

        attrs['tz'] = tz
        attrs['windows'] = windows
        return attrs


class LegRowSerializer(serializers.Serializer):
    """
    Flatten a single Leg into a schedule row.

    Each row carries the parent load's identity, this leg's owner (carrier +
    driver, or null when unassigned), this leg's own stops, and condensed
    summaries of the surrounding legs split into ``previous_legs`` / ``next_legs``.

    The view must precompute, per leg instance, ``_ordered_siblings`` (the full
    ordered list of *all* the load's legs, including ones that never become their
    own row) and ``_seq_index`` (this leg's 0-based position within that full
    list) so representation is O(1) and free of extra queries.

    Because only legs with a stop in a requested window are emitted as rows,
    ``sequence_index`` denotes position in the *full* trip and may be sparse
    across the response: a row can have ``sequence_index == 1`` with no
    ``sequence_index == 0`` row present. ``previous_legs`` / ``next_legs`` are
    still sliced from the full ``_ordered_siblings`` list, so off-window siblings
    appear there for context even though they have no row of their own.
    """

    def to_representation(self, leg):
        load = leg.load
        ordered = getattr(leg, '_ordered_siblings', None) or order_legs(load)
        seq_index = getattr(leg, '_seq_index', ordered.index(leg))
        assignment = _leg_assignment(leg)

        if load.customer_id is not None:
            customer = {'id': load.customer_id, 'customer_name': load.customer.customer_name}
        else:
            customer = None

        return {
            'leg_id': leg.id,
            'sequence_index': seq_index,
            'reference_number': load.reference_number,
            'status': load.status,
            'bol_number': load.bol_number,
            'trip_id': load.trip_id,
            'customer': customer,
            'owner': _owner_detail(leg),
            'is_assigned': assignment is not None,
            'stops': StopDailySerializer(
                leg.stops.all(), many=True, context=self.context
            ).data,
            'previous_legs': [_summarize_leg(sib) for sib in ordered[:seq_index]],
            'next_legs': [_summarize_leg(sib) for sib in ordered[seq_index + 1:]],
        }

