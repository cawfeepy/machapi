from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from agno.run.base import RunContext
from agno.tools import Toolkit
from django.db.models import Q, Exists, OuterRef, Prefetch

from machtms.backend.legs.models import Leg, ShipmentAssignment
from machtms.backend.legs.utils import swap_shipment_assignment
from machtms.backend.loads.models import BillingStatus, Load, LoadStatus
from machtms.backend.routes.models import Stop


class SwapToolkit(Toolkit):
    """Toolkit for driver swap operations."""

    def __init__(self):
        super().__init__(name="swap_toolkit")
        self.register(self.get_load_assignment_info)
        self.register(self.swap_drivers_between_loads)

    def get_load_assignment_info(self, run_context: RunContext, reference_number: str) -> str:
        """Get load, leg, and current driver assignment info by reference number.

        Args:
            reference_number: The load's reference number

        Returns:
            Load info with leg and driver assignment details
        """
        organization = run_context.dependencies["organization"]
        load = Load.objects.filter(
            organization=organization,
            reference_number=reference_number
        ).prefetch_related('legs__shipment_assignment__driver').first()

        if not load:
            return f"Load {reference_number} not found."

        result = f"Load {reference_number} (ID: {load.id}):\n"
        for leg in load.legs.all():
            assignment = getattr(leg, 'shipment_assignment', None)
            if assignment:
                driver = assignment.driver
                result += f"  - Leg {leg.id}: Driver {driver.first_name} {driver.last_name} (ID: {driver.id})\n"
            else:
                result += f"  - Leg {leg.id}: No driver assigned\n"
        return result

    def swap_drivers_between_loads(self, run_context: RunContext, load1_reference: str, load2_reference: str) -> str:
        """Swap drivers between two loads using their reference numbers.

        Both loads must exist and have exactly one leg with an assigned driver.

        Args:
            load1_reference: Reference number of first load
            load2_reference: Reference number of second load

        Returns:
            Success message or error description
        """
        organization = run_context.dependencies["organization"]
        load1 = Load.objects.filter(
            organization=organization,
            reference_number=load1_reference
        ).prefetch_related('legs__shipment_assignment__driver').first()

        load2 = Load.objects.filter(
            organization=organization,
            reference_number=load2_reference
        ).prefetch_related('legs__shipment_assignment__driver').first()

        if not load1:
            return f"Load {load1_reference} not found."
        if not load2:
            return f"Load {load2_reference} not found."

        leg1 = load1.legs.filter(shipment_assignment__isnull=False).first()
        leg2 = load2.legs.filter(shipment_assignment__isnull=False).first()

        if not leg1 or not leg1.shipment_assignment:
            return f"Load {load1_reference} has no driver assigned."
        if not leg2 or not leg2.shipment_assignment:
            return f"Load {load2_reference} has no driver assigned."

        driver1 = leg1.shipment_assignment.driver
        driver2 = leg2.shipment_assignment.driver

        swap_data = [
            {'leg_id': leg1.id, 'driver_id': driver2.id},
            {'leg_id': leg2.id, 'driver_id': driver1.id},
        ]

        swap_shipment_assignment(swap_data, organization)

        return (
            f"Swap completed successfully.\n"
            f"  - {load1_reference}: Now assigned to {driver2.first_name} {driver2.last_name}\n"
            f"  - {load2_reference}: Now assigned to {driver1.first_name} {driver1.last_name}"
        )


class LoadToolkit(Toolkit):
    """Toolkit for querying and searching loads."""

    PICKUP_ACTIONS = ['LL', 'HL', 'EMPP', 'HUBP']

    def __init__(self):
        super().__init__(name="load_toolkit")
        self.register(self.get_todays_loads)
        self.register(self.search_loads)

    @staticmethod
    def _format_load(load, display_tz, include_date=False):
        """Format a single load into a readable string.

        Args:
            load: Load instance with prefetched legs/stops/assignments.
            display_tz: ZoneInfo timezone for displaying times.
            include_date: If True, include the full date with time.

        Returns:
            Formatted string representation of the load.
        """
        customer_name = load.customer.customer_name if load.customer else "No customer"
        lines = [
            f"Load {load.reference_number} | Customer: {customer_name} "
            f"| Status: {load.get_status_display()} "
            f"| Billing: {load.get_billing_status_display()}"
        ]

        for leg in load.legs.all():
            assignment = getattr(leg, 'shipment_assignment', None)
            if assignment:
                driver = assignment.driver
                carrier = assignment.carrier
                driver_str = f"{driver.first_name} {driver.last_name}"
                carrier_str = carrier.carrier_name
            else:
                driver_str = "Unassigned"
                carrier_str = "Unassigned"

            lines.append(f"  Leg {leg.pk}: Driver: {driver_str} | Carrier: {carrier_str}")

            for stop in leg.stops.all():
                local_start = stop.start_range.astimezone(display_tz)
                if include_date:
                    time_str = local_start.strftime("%m/%d/%Y %I:%M %p %Z")
                else:
                    time_str = local_start.strftime("%I:%M %p %Z")
                address = stop.address
                addr_str = f"{address.street}, {address.city}, {address.state} {address.zip_code}"
                lines.append(
                    f"    Stop {stop.stop_number}: {stop.get_action_display()} "
                    f"@ {addr_str} | {time_str}"
                )

        return "\n".join(lines)

    @staticmethod
    def _base_queryset(organization):
        """Return base load queryset scoped to the organization with prefetches."""
        return (
            Load.objects
            .filter(organization=organization)
            .select_related('customer')
            .prefetch_related(
                Prefetch(
                    'legs',
                    queryset=Leg.objects.prefetch_related(
                        'shipment_assignment__driver',
                        'shipment_assignment__carrier',
                        Prefetch(
                            'stops',
                            queryset=Stop.objects.select_related('address').order_by('stop_number'),
                        ),
                    ).order_by('pk'),
                ),
            )
        )

    def get_todays_loads(self, run_context: RunContext) -> str:
        """Get all loads scheduled for pickup today (Pacific Time).

        Returns:
            A formatted list of today's loads with their details.
        """
        organization = run_context.dependencies["organization"]
        pt = ZoneInfo("America/Los_Angeles")
        now_pt = datetime.now(pt)
        today_start = now_pt.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        loads = (
            self._base_queryset(organization)
            .filter(
                legs__stops__action__in=self.PICKUP_ACTIONS,
                legs__stops__start_range__gte=today_start,
                legs__stops__start_range__lt=today_end,
            )
            .distinct()
        )

        if not loads.exists():
            return "No loads scheduled for pickup today."

        result_lines = [f"Today's Loads ({now_pt.strftime('%m/%d/%Y')}) — {len(loads)} load(s):\n"]
        for load in loads:
            result_lines.append(self._format_load(load, pt, include_date=False))
            result_lines.append("")

        return "\n".join(result_lines)

    def search_loads(
        self,
        run_context: RunContext,
        customer_name: str = "",
        carrier_name: str = "",
        driver_name: str = "",
        street_address: str = "",
        status: str = "",
        billing_status: str = "",
    ) -> str:
        """Search for loads by various criteria. At least one criterion is required.

        Args:
            customer_name: Filter by customer name (partial, case-insensitive).
            carrier_name: Filter by carrier name (partial, case-insensitive).
            driver_name: Filter by driver first or last name (partial, case-insensitive).
            street_address: Filter by stop street address (partial, case-insensitive).
            status: Filter by exact load status (e.g. 'pending', 'dispatched').
            billing_status: Filter by exact billing status (e.g. 'billed', 'paid').

        Returns:
            Formatted search results or an error/no-results message.
        """
        if not any([customer_name, carrier_name, driver_name, street_address, status, billing_status]):
            return "Error: At least one search criterion is required."

        valid_statuses = [choice[0] for choice in LoadStatus.choices]
        if status and status not in valid_statuses:
            return f"Error: Invalid status '{status}'. Valid options: {', '.join(valid_statuses)}"

        valid_billing = [choice[0] for choice in BillingStatus.choices]
        if billing_status and billing_status not in valid_billing:
            return f"Error: Invalid billing_status '{billing_status}'. Valid options: {', '.join(valid_billing)}"

        organization = run_context.dependencies["organization"]
        qs = self._base_queryset(organization)

        if customer_name:
            qs = qs.filter(customer__customer_name__icontains=customer_name)
        if carrier_name:
            qs = qs.filter(
                Exists(
                    ShipmentAssignment.objects.filter(
                        leg__load=OuterRef('pk'),
                        carrier__carrier_name__icontains=carrier_name,
                    )
                )
            )
        if driver_name:
            qs = qs.filter(
                Exists(
                    ShipmentAssignment.objects.filter(
                        leg__load=OuterRef('pk'),
                    ).filter(
                        Q(driver__first_name__icontains=driver_name)
                        | Q(driver__last_name__icontains=driver_name)
                    )
                )
            )
        if street_address:
            qs = qs.filter(
                Exists(
                    Stop.objects.filter(
                        leg__load=OuterRef('pk'),
                        address__street__icontains=street_address,
                    )
                )
            )
        if status:
            qs = qs.filter(status=status)
        if billing_status:
            qs = qs.filter(billing_status=billing_status)

        loads = qs[:25]

        if not loads:
            return "No loads found matching your search criteria."

        pt = ZoneInfo("America/Los_Angeles")
        result_lines = [f"Search Results — {len(loads)} load(s):\n"]
        for load in loads:
            result_lines.append(self._format_load(load, pt, include_date=True))
            result_lines.append("")

        return "\n".join(result_lines)
