from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Exists, OuterRef, Subquery, Prefetch
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from machtms.core.base.mixins import TMSViewMixin
from machtms.backend.loads.models import Load
from machtms.backend.legs.models import Leg, ShipmentAssignment
from machtms.backend.routes.models import Stop
from machtms.backend.loads.serializers import (
    LoadSerializer,
    LoadDailySerializer,
)
from machtms.backend.loads.openapi_doc import (
    CALENDAR_DAY_EXAMPLES,
    CALENDAR_WEEK_EXAMPLES,
)

# Actions that represent pickup stops
PICKUP_ACTIONS = ['LL', 'HL', 'EMPP', 'HUBP']

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
        summary="Get loads for a specific day",
        description=(
            "Returns loads that have at least one pickup stop on the specified date. "
            "Loads are sorted with unassigned legs first, then by earliest pickup time. "
            "Use this endpoint when the user clicks on a specific day in the calendar."
        ),
        parameters=[
            OpenApiParameter(
                name='date',
                type=str,
                location=OpenApiParameter.QUERY,
                description='The date to get loads for (YYYY-MM-DD). Defaults to today.',
                required=False,
                examples=[
                    OpenApiExample(
                        'Specific date',
                        value='2024-02-05',
                        description='Get loads for February 5th, 2024',
                    ),
                ],
            ),
        ],
        examples=CALENDAR_DAY_EXAMPLES,
    )
    @action(detail=False, methods=['get'], url_path='calendar-day')
    def calendar_day(self, request):
        """
        Returns loads for a specific day.

        Used when the frontend displays a single day's loads (e.g., user clicks Wednesday).
        """
        # 1. Parse date parameter
        date_param = request.query_params.get('date')
        day_start, day_end = self._get_day_boundaries(date_param)

        # 2. Build annotated queryset for this day
        base_queryset = self.get_queryset()
        queryset = self._get_calendar_day_queryset(base_queryset, day_start, day_end)

        # 3. Serialize loads
        serializer = LoadDailySerializer(queryset, many=True)
        loads_data = serializer.data

        # 4. Calculate summary stats
        total_loads = len(loads_data)
        unassigned_count = sum(1 for load in loads_data if load.get('has_unassigned_leg'))

        # 5. Build response
        response_data = {
            'date': day_start.date().isoformat(),
            'day_name': day_start.strftime('%A').lower(),
            'total_loads': total_loads,
            'unassigned_count': unassigned_count,
            'loads': loads_data,
        }

        return Response(response_data)

    def _get_day_boundaries(self, date_param):
        """Calculate day start and end boundaries."""
        if date_param:
            try:
                parsed_date = datetime.fromisoformat(date_param)
                day_start = timezone.make_aware(
                    datetime.combine(parsed_date.date(), datetime.min.time())
                )
            except ValueError:
                # Invalid date format, fall back to today
                day_start = timezone.make_aware(
                    datetime.combine(timezone.now().date(), datetime.min.time())
                )
        else:
            day_start = timezone.make_aware(
                datetime.combine(timezone.now().date(), datetime.min.time())
            )

        day_end = day_start + timedelta(days=1)
        return day_start, day_end

    def _get_calendar_day_queryset(self, base_queryset, day_start, day_end):
        """Build the annotated and prefetched queryset for a single day."""

        # Subquery: Does this load have at least one leg without a shipment assignment?
        unassigned_leg_subquery = Leg.objects.filter(
            load=OuterRef('pk')
        ).exclude(
            shipment_assignment__isnull=False
        )

        # Subquery: First pickup time for this load on this day
        first_pickup_on_day = Stop.objects.filter(
            leg__load=OuterRef('pk'),
            action__in=PICKUP_ACTIONS,
            start_range__gte=day_start,
            start_range__lt=day_end,
        ).order_by('start_range').values('start_range')[:1]

        return base_queryset.filter(
            legs__stops__action__in=PICKUP_ACTIONS,
            legs__stops__start_range__gte=day_start,
            legs__stops__start_range__lt=day_end,
        ).annotate(
            has_unassigned_leg=Exists(unassigned_leg_subquery),
            first_pickup_time=Subquery(first_pickup_on_day),
        ).distinct().select_related(
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
        ).order_by(
            '-has_unassigned_leg',
            'first_pickup_time',
        )

    @extend_schema(
        summary="Get loads for calendar week view",
        description=(
            "Returns loads grouped by day for a Sunday-Saturday week. "
            "Filters loads that have at least one pickup stop within the week. "
            "Within each day, loads are sorted with unassigned legs first, "
            "then by earliest pickup time. Loads with pickups on multiple days "
            "will appear in each relevant day's array."
        ),
        parameters=[
            OpenApiParameter(
                name='week_start',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Sunday of the desired week (YYYY-MM-DD). Defaults to current week.',
                required=False,
                examples=[
                    OpenApiExample(
                        'Specific week',
                        value='2024-02-04',
                        description='Get loads for the week of February 4th, 2024 (Sunday)',
                    ),
                ],
            ),
        ],
        examples=CALENDAR_WEEK_EXAMPLES,
    )
    @action(detail=False, methods=['get'], url_path='calendar-week')
    def calendar_week(self, request):
        """
        Returns loads organized by day for the specified week.
        """
        # 1. Parse week_start parameter
        week_start_param = request.query_params.get('week_start')
        week_start, week_end = self._get_week_boundaries(week_start_param)

        # 2. Build annotated queryset
        base_queryset = self.get_queryset()
        queryset = self._get_calendar_week_queryset(base_queryset, week_start, week_end)

        # 3. Serialize all loads
        serializer = LoadDailySerializer(queryset, many=True)
        loads_data = serializer.data

        # 4. Group by day
        days = self._group_loads_by_day(loads_data, week_start)

        # 5. Calculate summary stats
        total_loads = len(loads_data)
        unassigned_count = sum(1 for load in loads_data if load.get('has_unassigned_leg'))

        # 6. Build response
        response_data = {
            'week_start': week_start.date().isoformat(),
            'week_end': (week_end - timedelta(days=1)).date().isoformat(),
            'days': days,
            'total_loads': total_loads,
            'unassigned_count': unassigned_count,
        }

        return Response(response_data)

    def _get_week_boundaries(self, week_start_param):
        """Calculate Sunday-Saturday week boundaries."""
        if week_start_param:
            try:
                parsed_date = datetime.fromisoformat(week_start_param)
                week_start = timezone.make_aware(
                    datetime.combine(parsed_date.date(), datetime.min.time())
                )
            except ValueError:
                # Invalid date format, fall back to current week
                week_start = self._get_current_week_sunday()
        else:
            week_start = self._get_current_week_sunday()

        week_end = week_start + timedelta(days=7)
        return week_start, week_end

    def _get_current_week_sunday(self):
        """Get the Sunday of the current week."""
        today = timezone.now().date()
        days_since_sunday = (today.weekday() + 1) % 7
        sunday = today - timedelta(days=days_since_sunday)
        return timezone.make_aware(datetime.combine(sunday, datetime.min.time()))

    def _get_calendar_week_queryset(self, base_queryset, week_start, week_end):
        """Build the annotated and prefetched queryset for calendar view."""

        # Subquery: Does this load have at least one leg without a shipment assignment?
        unassigned_leg_subquery = Leg.objects.filter(
            load=OuterRef('pk')
        ).exclude(
            shipment_assignment__isnull=False
        )

        # Subquery: First pickup time for this load within the week
        first_pickup_in_week = Stop.objects.filter(
            leg__load=OuterRef('pk'),
            action__in=PICKUP_ACTIONS,
            start_range__gte=week_start,
            start_range__lt=week_end,
        ).order_by('start_range').values('start_range')[:1]

        return base_queryset.filter(
            legs__stops__action__in=PICKUP_ACTIONS,
            legs__stops__start_range__gte=week_start,
            legs__stops__start_range__lt=week_end,
        ).annotate(
            has_unassigned_leg=Exists(unassigned_leg_subquery),
            first_pickup_time=Subquery(first_pickup_in_week),
        ).distinct().select_related(
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
        ).order_by(
            '-has_unassigned_leg',
            'first_pickup_time',
        )

    def _group_loads_by_day(self, loads_data, week_start):
        """Group serialized loads by day of the week."""
        # Initialize days structure (Sunday = 0, Saturday = 6)
        day_names = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        days = {name: [] for name in day_names}

        for load in loads_data:
            # Find which days this load has pickup stops
            pickup_days = set()
            for leg in load.get('legs', []):
                for stop in leg.get('stops', []):
                    if stop.get('action') in PICKUP_ACTIONS:
                        start_range = stop.get('start_range')
                        if start_range:
                            # Handle ISO format string
                            if isinstance(start_range, str):
                                stop_time = datetime.fromisoformat(start_range.replace('Z', '+00:00'))
                            else:
                                stop_time = start_range
                            # Calculate day index (0 = Sunday)
                            day_offset = (stop_time.date() - week_start.date()).days
                            if 0 <= day_offset < 7:
                                pickup_days.add(day_offset)

            # Add load to each day it has a pickup
            for day_index in pickup_days:
                days[day_names[day_index]].append(load)

        # Sort each day's loads (unassigned first, then by first_pickup_time)
        for day_name in day_names:
            days[day_name].sort(
                key=lambda x: (not x.get('has_unassigned_leg', False), x.get('first_pickup_time') or '')
            )

        return days
