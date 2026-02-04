from agno.tools import Toolkit

from machtms.backend.legs.models import ShipmentAssignment
from machtms.backend.legs.utils import swap_shipment_assignment
from machtms.backend.loads.models import Load


class SwapToolkit(Toolkit):
    """Toolkit for driver swap operations."""

    def __init__(self, organization=None):
        super().__init__(name="swap_toolkit")
        self.organization = organization
        self.register(self.get_load_assignment_info)
        self.register(self.swap_drivers_between_loads)

    def get_load_assignment_info(self, reference_number: str) -> str:
        """Get load, leg, and current driver assignment info by reference number.

        Args:
            reference_number: The load's reference number

        Returns:
            Load info with leg and driver assignment details
        """
        load = Load.objects.filter(
            organization=self.organization,
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

    def swap_drivers_between_loads(self, load1_reference: str, load2_reference: str) -> str:
        """Swap drivers between two loads using their reference numbers.

        Both loads must exist and have exactly one leg with an assigned driver.

        Args:
            load1_reference: Reference number of first load
            load2_reference: Reference number of second load

        Returns:
            Success message or error description
        """
        load1 = Load.objects.filter(
            organization=self.organization,
            reference_number=load1_reference
        ).prefetch_related('legs__shipment_assignment__driver').first()

        load2 = Load.objects.filter(
            organization=self.organization,
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

        swap_shipment_assignment(swap_data, self.organization)

        return (
            f"Swap completed successfully.\n"
            f"  - {load1_reference}: Now assigned to {driver2.first_name} {driver2.last_name}\n"
            f"  - {load2_reference}: Now assigned to {driver1.first_name} {driver1.last_name}"
        )
