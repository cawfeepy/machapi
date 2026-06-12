from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Exists, OuterRef, Subquery, Prefetch, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
)
from machtms.core.base.mixins import TMSViewMixin
from machtms.backend.loads.models import Load
from machtms.backend.legs.models import Leg, ShipmentAssignment
from machtms.backend.routes.models import Stop
from machtms.backend.loads.serializers import (
    LoadSerializer,
    LegScheduleQuerySerializer,
    LegRowSerializer,
    order_legs,
    leg_in_windows,
    leg_earliest_start,
)
from machtms.backend.loads.openapi_doc import (
    CALENDAR_DAY_EXAMPLES,
    CALENDAR_WEEK_EXAMPLES,
)

# Actions that represent pickup stops
PICKUP_ACTIONS = ['LL', 'HL', 'EMPP', 'HUBP']

# ---------------------------------------------------------------------------
# OpenAPI response schema for the leg-schedule endpoint.
#
# leg_schedule returns hand-built dicts (not a registered serializer), so the
# response shape is described here as a raw OpenAPI object. Keys are declared
# in snake_case to match the actual JSON exactly -- the camelize postprocessing
# hook only rewrites introspected serializer fields, never raw dict values, so
# a serializer-based schema here would mismatch the real (snake_case) payload.
# ---------------------------------------------------------------------------
_SIBLING_STOP_SCHEMA = {
    'type': 'object',
    'properties': {
        'label': {'type': 'string', 'example': 'Walmart DC - Dallas, TX'},
        'action': {'type': 'string', 'example': 'LL'},
        'action_display': {'type': 'string', 'example': 'LIVE LOAD'},
        'start_range': {'type': 'string', 'format': 'date-time', 'nullable': True},
        'end_range': {'type': 'string', 'format': 'date-time', 'nullable': True},
    },
}

_SIBLING_LEG_SCHEMA = {
    'type': 'object',
    'properties': {
        'leg_id': {'type': 'integer'},
        'sequence_index': {'type': 'integer'},
        'owner': {
            'type': 'string',
            'description': '"<carrier_name> / <driver_full_name>" or "unassigned".',
            'example': 'Speedy Freight / John Doe',
        },
        'stops': {'type': 'array', 'items': _SIBLING_STOP_SCHEMA},
    },
}

_OWN_STOP_SCHEMA = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer'},
        'stop_number': {'type': 'integer'},
        'address': {'type': 'object', 'description': 'Full AddressSerializer object.'},
        'start_range': {'type': 'string', 'format': 'date-time', 'nullable': True},
        'end_range': {'type': 'string', 'format': 'date-time', 'nullable': True},
        'action': {'type': 'string'},
        'action_display': {'type': 'string'},
        'po_numbers': {'type': 'string'},
    },
}

_LEG_ROW_SCHEMA = {
    'type': 'object',
    'properties': {
        'leg_id': {'type': 'integer'},
        'sequence_index': {
            'type': 'integer',
            'description': '0-based position of this leg within the load, ordered by earliest stop.',
        },
        'reference_number': {'type': 'string'},
        'status': {'type': 'string'},
        'bol_number': {'type': 'string'},
        'trip_id': {'type': 'string'},
        'customer': {
            'type': 'object',
            'nullable': True,
            'properties': {
                'id': {'type': 'integer'},
                'customer_name': {'type': 'string'},
            },
        },
        'owner': {
            'type': 'object',
            'nullable': True,
            'description': 'This leg\'s carrier + driver, or null when unassigned.',
            'properties': {
                'carrier': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'carrier_name': {'type': 'string'},
                    },
                },
                'driver': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'full_name': {'type': 'string'},
                    },
                },
            },
        },
        'is_assigned': {'type': 'boolean'},
        'stops': {'type': 'array', 'items': _OWN_STOP_SCHEMA},
        'previous_legs': {'type': 'array', 'items': _SIBLING_LEG_SCHEMA},
        'next_legs': {'type': 'array', 'items': _SIBLING_LEG_SCHEMA},
    },
}

LEG_SCHEDULE_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'count': {'type': 'integer'},
        'results': {'type': 'array', 'items': _LEG_ROW_SCHEMA},
    },
}

LEG_SCHEDULE_RESPONSE_EXAMPLE = OpenApiExample(
    'Chronological stream interleaving two loads',
    value={
        'count': 2,
        'results': [
            {
                'leg_id': 20,
                'sequence_index': 0,
                'reference_number': 'REF-000456',
                'status': 'assigned',
                'bol_number': 'BOL-000456',
                'trip_id': 'TRIP-77',
                'customer': {'id': 9, 'customer_name': 'Northwind Traders'},
                'owner': {
                    'carrier': {'id': 30, 'carrier_name': 'Cross Country Hauling'},
                    'driver': {'id': 60, 'full_name': 'Maria Lopez'},
                },
                'is_assigned': True,
                'stops': [
                    {
                        'id': 200, 'stop_number': 1,
                        'address': {'id': 14, 'place_name': 'Costco DC', 'city': 'Denver', 'state': 'CO'},
                        'start_range': '2025-06-01T14:00:00Z', 'end_range': '2025-06-01T16:00:00Z',
                        'action': 'LL', 'action_display': 'LIVE LOAD', 'po_numbers': 'PO-9',
                    },
                ],
                'previous_legs': [],
                'next_legs': [],
            },
            {
                'leg_id': 11,
                'sequence_index': 1,
                'reference_number': 'REF-000123',
                'status': 'assigned',
                'bol_number': 'BOL-000123',
                'trip_id': 'TRIP-99',
                'customer': {'id': 5, 'customer_name': 'Acme Logistics'},
                'owner': None,
                'is_assigned': False,
                'stops': [
                    {
                        'id': 101, 'stop_number': 1,
                        'address': {'id': 8, 'place_name': 'Target DC', 'city': 'Phoenix', 'state': 'AZ'},
                        'start_range': '2025-06-01T23:00:00Z', 'end_range': None,
                        'action': 'LU', 'action_display': 'LIVE UNLOAD', 'po_numbers': '',
                    },
                ],
                'previous_legs': [
                    {
                        'leg_id': 10, 'sequence_index': 0, 'owner': 'Speedy Freight / John Doe',
                        'stops': [{
                            'label': 'Walmart DC - Dallas, TX', 'action': 'LL',
                            'action_display': 'LIVE LOAD',
                            'start_range': '2025-05-31T15:00:00Z', 'end_range': '2025-05-31T17:00:00Z',
                        }],
                    },
                ],
                'next_legs': [],
            },
        ],
    },
    response_only=True,
)

class LoadViewSet(TMSViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing Load objects.

    Provides CRUD operations for loads with organization-based filtering.
    """
    queryset = Load.objects.all()
    serializer_class = LoadSerializer

    def get_serializer_class(self):
        """
        Return appropriate serializer class based on action.
        """
        # if self.action == 'list':
        #     return LoadListSerializer
        # elif self.action == 'retrieve':
        #     return LoadDetailSerializer
        # elif self.action in ['create', 'update', 'partial_update']:
        #     return LoadWriteSerializer
        return LoadSerializer  # Default fallback


    @extend_schema(
        summary="Flat per-leg schedule for a set of dates",
        description=(
            "Returns one row per leg whose OWN stop (pickup or delivery) starts "
            "within any of the requested local-day windows. Results are a single "
            "flat CHRONOLOGICAL stream ordered by each leg's earliest stop time "
            "(earliest first), tie-broken by leg id -- rows are NOT grouped by "
            "load, so legs from different loads may interleave. Legs whose own "
            "stops all fall outside the windows (or that have no stops) do NOT get "
            "their own row, but still appear inside the previous_legs / next_legs "
            "of the legs that do, providing full-trip context. Each row carries "
            "the load's identity, the leg's owner (carrier + driver, or null when "
            "unassigned), the leg's stops, and condensed summaries of the "
            "surrounding legs (previous_legs / next_legs). Note sequence_index is "
            "the leg's position within its full trip and may be non-contiguous "
            "across rows."
        ),
        parameters=[
            OpenApiParameter(
                name='dates',
                type=str,
                location=OpenApiParameter.QUERY,
                description='One or more dates (YYYY-MM-DD). May be repeated for non-consecutive days.',
                required=True,
                many=True,
                examples=[
                    OpenApiExample('Two non-consecutive days', value=['2025-06-01', '2025-06-16']),
                ],
            ),
            OpenApiParameter(
                name='timezone',
                type=str,
                location=OpenApiParameter.QUERY,
                description='IANA timezone the dates are expressed in (e.g. America/Los_Angeles).',
                required=True,
                examples=[OpenApiExample('Pacific', value='America/Los_Angeles')],
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=LEG_SCHEDULE_RESPONSE_SCHEMA,
                description='Flat list of leg rows wrapped in a count/results envelope.',
                examples=[LEG_SCHEDULE_RESPONSE_EXAMPLE],
            ),
        },
    )
    @action(detail=False, methods=['get'], url_path='leg-schedule')
    def leg_schedule(self, request):
        """Return loads flattened to one row per leg for the requested dates."""
        # 1. Validate query params -> UTC day windows
        query = LegScheduleQuerySerializer(data={
            'dates': request.query_params.getlist('dates'),
            'timezone': request.query_params.get('timezone'),
        })
        query.is_valid(raise_exception=True)
        windows = query.validated_data['windows']

        # 2. A load matches if ANY of its stops (pickup or delivery) starts within
        #    ANY requested window. Combine the windows with OR.
        window_q = Q()
        for start, end in windows:
            window_q |= Q(legs__stops__start_range__range=(start, end))

        queryset = self.get_queryset().filter(window_q).distinct().select_related(
            'customer',
        ).prefetch_related(
            Prefetch(
                'legs',
                queryset=Leg.objects.prefetch_related(
                    Prefetch(
                        'stops',
                        queryset=Stop.objects.select_related('address').order_by('stop_number')
                    ),
                    Prefetch(
                        'shipment_assignment',
                        queryset=ShipmentAssignment.objects.select_related('carrier', 'driver')
                    ),
                ).order_by('pk')
            ),
        )

        # 3. Flatten loads -> legs. Per load we order ALL its legs into trip
        #    sequence and stash that full ordered list (+ each leg's position) on
        #    every leg, so previous_legs/next_legs always have full-trip context
        #    -- even for siblings that fall outside the window and never become a
        #    row. Only legs with a stop inside a requested window are emitted as
        #    rows. Precomputing here keeps the serializer O(1) and query-free.
        rows = []
        for load in queryset:
            ordered = order_legs(load)
            for index, leg in enumerate(ordered):
                leg._ordered_siblings = ordered
                leg._seq_index = index
                if leg_in_windows(leg, windows):
                    # An in-window leg always has a stop with a real start_range,
                    # so this key is never None (no datetime-vs-None comparison).
                    leg._row_sort_key = leg_earliest_start(leg)
                    rows.append(leg)

        # One flat chronological stream: every emitted leg ordered by its own
        # earliest stop, tie-broken by pk. Rows are NOT grouped by load -- a
        # multi-leg load's rows may be split apart by other loads' legs whose
        # pickups fall between them.
        rows.sort(key=lambda leg: (leg._row_sort_key, leg.pk))

        data = LegRowSerializer(rows, many=True, context={'request': request}).data
        return Response({'count': len(data), 'results': data})
