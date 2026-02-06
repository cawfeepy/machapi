from datetime import timedelta

from agno.tools import Toolkit
from agno.run.base import RunContext
from django.db.models import Count, Q
from django.utils import timezone

from machtms.backend.carriers.models import Carrier, Driver
from machtms.backend.legs.models import ShipmentAssignment


class CarrierDriverToolkit(Toolkit):
    """Toolkit for carrier and driver search operations."""

    def __init__(self):
        super().__init__(name="carrier_driver_toolkit")
        self.register(self.search_carriers)
        self.register(self.search_drivers)
        self.register(self.get_drivers_for_carrier)
        self.register(self.get_recent_driver_loads)
        self.register(self.list_carriers)
        self.register(self.list_drivers)
        self.register(self.get_recently_active_carriers)
        self.register(self.get_recently_active_drivers)

    def search_carriers(self, run_context: RunContext, carrier_name: str) -> str:
        """Search carriers by name (partial, case-insensitive).

        Args:
            carrier_name: Carrier name to search for.

        Returns:
            Formatted list of matching carriers with IDs and driver counts.
        """
        if not carrier_name:
            return "Error: Carrier name is required."

        organization = run_context.dependencies["organization"]
        carriers = (
            Carrier.objects
            .filter(
                organization=organization,
                carrier_name__icontains=carrier_name,
            )
            .prefetch_related('drivers')[:20]
        )

        if not carriers:
            return f"No carriers found matching '{carrier_name}'."

        lines = [f"Found {len(carriers)} carrier(s):"]
        for c in carriers:
            driver_count = c.drivers.count()
            lines.append(f"  ID {c.pk}: {c.carrier_name} | Drivers: {driver_count}")
        return "\n".join(lines)

    def search_drivers(self, run_context: RunContext, driver_name: str) -> str:
        """Search drivers by first or last name (partial, case-insensitive).

        Args:
            driver_name: Driver name to search for.

        Returns:
            Formatted list of matching drivers with carrier info.
        """
        if not driver_name:
            return "Error: Driver name is required."

        organization = run_context.dependencies["organization"]
        drivers = (
            Driver.objects
            .filter(organization=organization)
            .filter(
                Q(first_name__icontains=driver_name)
                | Q(last_name__icontains=driver_name)
            )
            .select_related('carrier')[:20]
        )

        if not drivers:
            return f"No drivers found matching '{driver_name}'."

        lines = [f"Found {len(drivers)} driver(s):"]
        for d in drivers:
            carrier_str = d.carrier.carrier_name if d.carrier else "No carrier"
            lines.append(
                f"  ID {d.pk}: {d.first_name} {d.last_name} "
                f"| Carrier: {carrier_str} (ID {d.carrier_id})"
            )
        return "\n".join(lines)

    def get_drivers_for_carrier(self, run_context: RunContext, carrier_id: int) -> str:
        """List all drivers for a specific carrier.

        Args:
            carrier_id: The carrier's ID.

        Returns:
            Formatted list of drivers belonging to the carrier.
        """
        organization = run_context.dependencies["organization"]
        try:
            carrier = Carrier.objects.get(pk=carrier_id, organization=organization)
        except Carrier.DoesNotExist:
            return f"Carrier ID {carrier_id} not found."

        drivers = carrier.drivers.filter(organization=organization)

        if not drivers:
            return f"No drivers found for carrier '{carrier.carrier_name}'."

        lines = [f"Drivers for {carrier.carrier_name} (ID {carrier.pk}):"]
        for d in drivers:
            lines.append(f"  ID {d.pk}: {d.first_name} {d.last_name} | Phone: {d.phone_number}")
        return "\n".join(lines)

    def get_recent_driver_loads(
        self,
        run_context: RunContext,
        driver_name: str,
        days_back: int = 7,
    ) -> str:
        """Get recent load assignments for a driver to help disambiguate.

        Args:
            driver_name: Driver name to search for.
            days_back: Number of days to look back (default 7).

        Returns:
            Formatted list of recent loads for matching drivers.
        """
        if not driver_name:
            return "Error: Driver name is required."

        organization = run_context.dependencies["organization"]
        cutoff = timezone.now() - timedelta(days=days_back)

        assignments = (
            ShipmentAssignment.objects
            .filter(
                organization=organization,
                leg__load__created_at__gte=cutoff,
            )
            .filter(
                Q(driver__first_name__icontains=driver_name)
                | Q(driver__last_name__icontains=driver_name)
            )
            .select_related('driver', 'carrier', 'leg__load')
            .order_by('-leg__load__created_at')[:20]
        )

        if not assignments:
            return f"No recent loads found for driver matching '{driver_name}' in the last {days_back} days."

        lines = [f"Recent loads for driver(s) matching '{driver_name}':"]
        for a in assignments:
            load = a.leg.load
            lines.append(
                f"  Driver: {a.driver.first_name} {a.driver.last_name} (ID {a.driver_id}) "
                f"| Load: {load.reference_number} | Carrier: {a.carrier.carrier_name} "
                f"| Created: {load.created_at.strftime('%m/%d/%Y')}"
            )
        return "\n".join(lines)

    def list_carriers(
        self,
        run_context: RunContext,
        limit: int = 20,
    ) -> str:
        """List all carriers for the organization, ordered by name.

        Args:
            limit: Maximum number of carriers to return (default 20).

        Returns:
            Formatted list of carriers with IDs and driver counts.
        """
        organization = run_context.dependencies["organization"]
        carriers = (
            Carrier.objects
            .filter(organization=organization)
            .prefetch_related('drivers')
            .order_by('carrier_name')[:limit]
        )

        if not carriers:
            return "No carriers found for this organization."

        lines = [f"Listing {len(carriers)} carrier(s):"]
        for c in carriers:
            driver_count = c.drivers.count()
            lines.append(f"  ID {c.pk}: {c.carrier_name} | Drivers: {driver_count}")
        return "\n".join(lines)

    def list_drivers(
        self,
        run_context: RunContext,
        limit: int = 20,
    ) -> str:
        """List all drivers for the organization, ordered by last name then first name.

        Args:
            limit: Maximum number of drivers to return (default 20).

        Returns:
            Formatted list of drivers with IDs and carrier info.
        """
        organization = run_context.dependencies["organization"]
        drivers = (
            Driver.objects
            .filter(organization=organization)
            .select_related('carrier')
            .order_by('last_name', 'first_name')[:limit]
        )

        if not drivers:
            return "No drivers found for this organization."

        lines = [f"Listing {len(drivers)} driver(s):"]
        for d in drivers:
            carrier_str = d.carrier.carrier_name if d.carrier else "No carrier"
            lines.append(
                f"  ID {d.pk}: {d.first_name} {d.last_name} "
                f"| Carrier: {carrier_str}"
            )
        return "\n".join(lines)

    def get_recently_active_carriers(
        self,
        run_context: RunContext,
        days_back: int = 30,
        limit: int = 20,
    ) -> str:
        """Get carriers with shipment assignments on loads created within the last N days.

        Args:
            days_back: Number of days to look back (default 30).
            limit: Maximum number of carriers to return (default 20).

        Returns:
            Formatted list of recently active carriers with assignment counts.
        """
        organization = run_context.dependencies["organization"]
        cutoff = timezone.now() - timedelta(days=days_back)

        carriers = (
            Carrier.objects
            .filter(
                organization=organization,
                shipment_assignments__leg__load__created_at__gte=cutoff,
            )
            .annotate(recent_assignment_count=Count('shipment_assignments'))
            .order_by('-recent_assignment_count')[:limit]
        )

        if not carriers:
            return f"No carriers with assignments in the last {days_back} days."

        lines = [f"Carriers active in the last {days_back} days:"]
        for c in carriers:
            lines.append(
                f"  ID {c.pk}: {c.carrier_name} "
                f"| Recent assignments: {c.recent_assignment_count}"
            )
        return "\n".join(lines)

    def get_recently_active_drivers(
        self,
        run_context: RunContext,
        days_back: int = 30,
        limit: int = 20,
    ) -> str:
        """Get drivers with shipment assignments on loads created within the last N days.

        Args:
            days_back: Number of days to look back (default 30).
            limit: Maximum number of drivers to return (default 20).

        Returns:
            Formatted list of recently active drivers with carrier and assignment counts.
        """
        organization = run_context.dependencies["organization"]
        cutoff = timezone.now() - timedelta(days=days_back)

        drivers = (
            Driver.objects
            .filter(
                organization=organization,
                shipment_assignments__leg__load__created_at__gte=cutoff,
            )
            .select_related('carrier')
            .annotate(recent_assignment_count=Count('shipment_assignments'))
            .order_by('-recent_assignment_count')[:limit]
        )

        if not drivers:
            return f"No drivers with assignments in the last {days_back} days."

        lines = [f"Drivers active in the last {days_back} days:"]
        for d in drivers:
            carrier_str = d.carrier.carrier_name if d.carrier else "No carrier"
            lines.append(
                f"  ID {d.pk}: {d.first_name} {d.last_name} "
                f"| Carrier: {carrier_str} "
                f"| Recent assignments: {d.recent_assignment_count}"
            )
        return "\n".join(lines)
