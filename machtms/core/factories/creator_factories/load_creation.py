"""
LoadCreationFactory - Orchestrates complete load creation workflow.

This module provides the LoadCreationFactory class which uses composition
to coordinate existing factories (LoadFactory, CustomerFactory, LegFactory, etc.)
to build complete loads with all related objects.

Example usage:
    from machtms.core.factories import LoadCreationFactory

    factory = LoadCreationFactory(
        stop_length=2,
        carrier_factory=carrier_creator,
        address_factory=address_creator
    )
    result = factory.create_complete_load()
    # result contains: 'load', 'customer', 'leg', 'stops', 'assignment'
"""

import random
from datetime import timedelta
from typing import TYPE_CHECKING, List, Optional, Protocol, Tuple, TypedDict

from django.db import transaction
from django.utils import timezone

from machtms.backend.customers.models import Customer
from machtms.backend.legs.models import Leg, ShipmentAssignment
from machtms.backend.loads.models import BillingStatus, Load, LoadStatus, TrailerType
from machtms.backend.routes.models import Stop
from machtms.core.factories.customer import CustomerFactory
from machtms.core.factories.leg import LegFactory, ShipmentAssignmentFactory
from machtms.core.factories.loads import LoadFactory
from machtms.core.factories.routes import StopFactory

if TYPE_CHECKING:
    from machtms.backend.addresses.models import Address
    from machtms.backend.carriers.models import Carrier, Driver


class CarrierFactoryProtocol(Protocol):
    """Protocol defining the interface for carrier factories."""

    def get_carrier_driver_pair(self) -> Tuple["Carrier", "Driver"]:
        """Return a carrier and driver pair for assignment."""
        ...


class AddressFactoryProtocol(Protocol):
    """Protocol defining the interface for address factories."""

    def get_address_tuple(self) -> Tuple["Address", ...]:
        """Return a tuple of addresses for stops."""
        ...


class LoadCreationResult(TypedDict):
    """Type definition for the result of create_complete_load."""

    customer: Customer
    load: Load
    leg: Optional[Leg]
    stops: List[Stop]
    assignment: Optional[ShipmentAssignment]


class LoadCreationFactory:
    """
    Factory for creating complete loads with all associated objects.

    This class orchestrates the creation of a full load hierarchy including:
    - Customer with address
    - Load with customer association
    - Leg with load association
    - Stops with addresses and proper actions
    - ShipmentAssignment with carrier/driver

    Attributes:
        stop_length: Number of stops per leg (2 or 3)
        carrier_factory: Factory providing (carrier, driver) pairs
        address_factory: Factory providing address tuples
        create_legs: Whether to create legs/stops/assignments (default True)
    """

    FIRST_STOP_ACTIONS: List[str] = ["LL", "HL"]
    MIDDLE_STOP_ACTIONS: List[str] = ["HUBP", "HUBD"]
    LAST_STOP_ACTIONS: List[str] = ["LU", "LD"]

    def __init__(
        self,
        stop_length: Optional[int] = None,
        carrier_factory: Optional[CarrierFactoryProtocol] = None,
        address_factory: Optional[AddressFactoryProtocol] = None,
        create_legs: bool = True,
    ) -> None:
        """
        Initialize LoadCreationFactory with configuration.

        Args:
            stop_length: Number of stops per leg (must be 2 or 3).
                        Required when create_legs=True, can be None otherwise.
            carrier_factory: Object with get_carrier_driver_pair() method
                            returning Tuple[Carrier, Driver].
                            Required when create_legs=True, can be None otherwise.
            address_factory: Object with get_address_tuple() method
                            returning Tuple[Address, ...].
                            Required when create_legs=True, can be None otherwise.
            create_legs: Whether to create legs, stops, and assignments.
                        When False, only customer and load are created.
                        Default is True for backward compatibility.

        Raises:
            ValueError: If create_legs=True and stop_length is not 2 or 3
            ValueError: If create_legs=True and carrier_factory or address_factory is None
        """
        self.create_legs = create_legs

        if create_legs:
            if stop_length not in (2, 3):
                raise ValueError(f"stop_length must be 2 or 3, got {stop_length}")
            if carrier_factory is None:
                raise ValueError("carrier_factory cannot be None when create_legs=True")
            if address_factory is None:
                raise ValueError("address_factory cannot be None when create_legs=True")

        self.stop_length = stop_length
        self.carrier_factory = carrier_factory
        self.address_factory = address_factory

    def create_customer(self) -> Customer:
        """
        Create a customer with an associated address.

        Uses CustomerFactory which internally creates an address via AddressFactory.
        The customer gets a unique address (not from the address pool).

        Returns:
            Customer: Saved Customer instance with address
        """
        return CustomerFactory.create()

    def create_load(self, customer: Customer) -> Load:
        """
        Create a load associated with the given customer.

        Generates a load with:
        - Auto-generated reference_number and bol_number (via factory sequences)
        - Status: PENDING (default for new loads)
        - Billing status: PENDING_DELIVERY (default for new loads)
        - Randomly selected trailer_type

        Args:
            customer: Customer instance to associate with the load

        Returns:
            Load: Saved Load instance
        """
        available_trailer_types = [
            choice[0] for choice in TrailerType.choices if choice[0]
        ]
        selected_trailer_type = (
            random.choice(available_trailer_types) if available_trailer_types else ""
        )

        return LoadFactory.create(
            customer=customer,
            status=LoadStatus.PENDING,
            billing_status=BillingStatus.PENDING_DELIVERY,
            trailer_type=selected_trailer_type,
        )

    def create_leg(self, load: Load) -> Leg:
        """
        Create a leg associated with the given load.

        Creates a single leg for the load. The leg will later have
        stops associated with it via create_stops().

        Args:
            load: Load instance to associate with the leg

        Returns:
            Leg: Saved Leg instance
        """
        return LegFactory.create(load=load)

    def _determine_stop_action(
        self, stop_index: int, total_stops: int
    ) -> str:
        """
        Determine the appropriate action for a stop based on its position.

        Args:
            stop_index: Zero-based index of the stop
            total_stops: Total number of stops in the leg

        Returns:
            Action code string (e.g., 'LL', 'LU', 'HUBP')
        """
        is_first_stop = stop_index == 0
        is_last_stop = stop_index == total_stops - 1

        if is_first_stop:
            return random.choice(self.FIRST_STOP_ACTIONS)
        elif is_last_stop:
            return random.choice(self.LAST_STOP_ACTIONS)
        else:
            return random.choice(self.MIDDLE_STOP_ACTIONS)

    def create_stops(self, leg: Leg) -> List[Stop]:
        """
        Create stops for the given leg.

        Gets addresses from the address_factory and creates Stop instances
        with proper sequencing and actions based on position:

        - First stop (stop_number=1): 'LL' (Live Load) or 'HL' (Hook Loaded)
        - Middle stop (stop_number=2, only for 3-stop legs): 'HUBP' or 'HUBD'
        - Last stop: 'LU' (Live Unload) or 'LD' (Drop Loaded)

        Each stop gets:
        - start_range: now + 1-7 days (random offset)
        - end_range: start_range + 2 hours

        Args:
            leg: Leg instance to associate stops with

        Returns:
            List[Stop]: List of saved Stop instances ordered by stop_number
        """
        address_tuple = self.address_factory.get_address_tuple()
        total_stops = len(address_tuple)

        stops: List[Stop] = []
        random_days_offset = random.randint(1, 7)
        base_date = timezone.now() + timedelta(days=random_days_offset)

        for stop_index, address in enumerate(address_tuple):
            stop_number = stop_index + 1
            action = self._determine_stop_action(stop_index, total_stops)

            hours_offset = 4 * stop_index
            start_range = base_date + timedelta(hours=hours_offset)
            end_range = start_range + timedelta(hours=2)

            stop = StopFactory.create(
                leg=leg,
                stop_number=stop_number,
                address=address,
                action=action,
                start_range=start_range,
                end_range=end_range,
            )
            stops.append(stop)

        return stops

    def assign_carrier_driver(self, leg: Leg) -> ShipmentAssignment:
        """
        Create a shipment assignment for the given leg.

        Gets a carrier/driver pair from the carrier_factory and creates
        a ShipmentAssignment linking them to the leg.

        Args:
            leg: Leg instance to assign carrier/driver to

        Returns:
            ShipmentAssignment: Saved ShipmentAssignment instance
        """
        carrier, driver = self.carrier_factory.get_carrier_driver_pair()

        return ShipmentAssignmentFactory.create(
            carrier=carrier,
            driver=driver,
            leg=leg,
        )

    @transaction.atomic
    def create_complete_load(self) -> LoadCreationResult:
        """
        Orchestrate the complete load creation workflow.

        Creates all objects in the proper sequence within a database transaction:
        1. Customer (with address)
        2. Load (associated with customer)
        3. Leg (associated with load) - only if create_legs=True
        4. Stops (associated with leg, using addresses from pool) - only if create_legs=True
        5. ShipmentAssignment (carrier/driver assigned to leg) - only if create_legs=True

        When create_legs=False, only steps 1-2 are executed and the result will have
        leg=None, stops=[], and assignment=None.

        The entire operation is wrapped in transaction.atomic() to ensure
        all-or-nothing behavior - if any step fails, all changes are rolled back.

        Returns:
            LoadCreationResult: Dictionary containing all created objects with keys:
                - 'customer': Customer instance
                - 'load': Load instance
                - 'leg': Leg instance or None (if create_legs=False)
                - 'stops': List of Stop instances or empty list (if create_legs=False)
                - 'assignment': ShipmentAssignment instance or None (if create_legs=False)

        Example:
            # Full load creation with legs
            factory = LoadCreationFactory(
                stop_length=2,
                carrier_factory=carrier_creator,
                address_factory=address_creator
            )
            result = factory.create_complete_load()
            print(f"Created load: {result['load'].reference_number}")
            print(f"With {len(result['stops'])} stops")

            # Load creation without legs
            factory = LoadCreationFactory(create_legs=False)
            result = factory.create_complete_load()
            print(f"Created load: {result['load'].reference_number}")
            print(f"Leg: {result['leg']}")  # None
        """
        customer = self.create_customer()
        load = self.create_load(customer)

        if self.create_legs:
            leg = self.create_leg(load)
            stops = self.create_stops(leg)
            assignment = self.assign_carrier_driver(leg)
        else:
            leg = None
            stops = []
            assignment = None

        return LoadCreationResult(
            customer=customer,
            load=load,
            leg=leg,
            stops=stops,
            assignment=assignment,
        )
