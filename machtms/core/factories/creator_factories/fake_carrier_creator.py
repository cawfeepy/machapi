"""
FakeCarrierCreator module for generating carriers with their drivers for load simulation.

This module provides the FakeCarrierCreator class that generates Carrier instances
along with associated Driver instances for use in load creation scenarios.
"""
import random
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple, TypeAlias

from machtms.backend.carriers.models import Carrier, Driver
from machtms.core.factories.carrier import CarrierFactory, DriverFactory

# Type aliases for clarity
CarrierList: TypeAlias = List[Carrier]
CarrierDriverPair: TypeAlias = Tuple[Carrier, Driver]


class HOSComplianceError(Exception):
    """Raised when no carrier/driver pair can satisfy HOS constraints."""


class DriverScheduleTracker:
    """
    Tracks driver pickup times per day and enforces an effective duty-window limit.

    Attributes:
        effective_window_hours: Maximum allowed span (in hours) between the earliest
            and latest pickup on a single day for one driver.
    """

    def __init__(self, effective_window_hours: float = 12.0) -> None:
        self.effective_window_hours = effective_window_hours
        # {driver_pk: {date: [datetime, ...]}}
        self._schedule: Dict[int, Dict[datetime, List[datetime]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def is_compliant(self, driver_pk: int, proposed_pickup: datetime) -> bool:
        """Return True if adding proposed_pickup keeps the driver within the window."""
        day = proposed_pickup.date()
        existing = self._schedule[driver_pk][day]
        if not existing:
            return True
        all_times = existing + [proposed_pickup]
        span = (max(all_times) - min(all_times)).total_seconds() / 3600.0
        return span <= self.effective_window_hours

    def record_pickup(self, driver_pk: int, pickup_datetime: datetime) -> None:
        """Record a pickup assignment for the given driver."""
        day = pickup_datetime.date()
        self._schedule[driver_pk][day].append(pickup_datetime)


class FakeCarrierCreator:
    """
    Creates and manages fake carriers with their drivers for load simulation.

    This class generates Carrier instances using CarrierFactory, each with 2-3
    randomly assigned drivers created via DriverFactory. The carriers are stored
    in a list for easy access by LoadCreationFactory.

    Attributes:
        carriers: List of Carrier instances, each with 2-3 associated drivers.

    Example:
        creator = FakeCarrierCreator(carriers_length=5)
        len(creator.carriers)  # 5 carriers
        carrier, driver = creator.get_carrier_driver_pair()
    """

    def __init__(
        self,
        carriers_length: int,
        max_drivers: int = 3,
        enforce_hos: bool = False,
        effective_window_hours: float = 12.0,
    ) -> None:
        """
        Initialize FakeCarrierCreator and create the specified number of carriers.

        Creates carriers_length number of carriers, each with 2-max_drivers drivers.

        Args:
            carriers_length: Number of carriers to create. Must be >= 1.
            max_drivers: Maximum number of drivers per carrier (min is always 2).
                        Default is 3, giving 2-3 drivers per carrier.
            enforce_hos: When True, enables HOS compliance checking via
                        get_compliant_carrier_driver_pair().
            effective_window_hours: Maximum span (hours) between earliest and latest
                        pickup on a single day for one driver. Default 12.0.

        Raises:
            ValueError: If carriers_length is less than 1.
        """
        if carriers_length < 1:
            raise ValueError("carriers_length must be at least 1")

        self.carriers: CarrierList = []
        self.max_drivers = max_drivers
        self.enforce_hos = enforce_hos
        self._schedule_tracker: Optional[DriverScheduleTracker] = None

        if enforce_hos:
            self._schedule_tracker = DriverScheduleTracker(effective_window_hours)

        # Create the specified number of carriers with drivers
        for _ in range(carriers_length):
            self.createDrivers()

    def createDrivers(self) -> Carrier:
        """
        Create a carrier with 2-3 randomly assigned drivers.

        Uses CarrierFactory to create a new Carrier instance and DriverFactory
        to create 2-3 Driver instances associated with that carrier. The carrier
        is appended to self.carriers list.

        Returns:
            The newly created Carrier instance with its associated drivers.

        Note:
            Each driver is persisted to the database with the carrier relationship
            established through the carrier ForeignKey.
        """
        # Create a new carrier
        carrier = CarrierFactory.create()

        # Determine random number of drivers (2 to max_drivers)
        num_drivers = random.randint(2, self.max_drivers)

        # Create drivers associated with this carrier
        for _ in range(num_drivers):
            DriverFactory.create(carrier=carrier)

        # Append carrier to our list
        self.carriers.append(carrier)

        return carrier

    def get_carrier_driver_pair(self) -> CarrierDriverPair:
        """
        Return a random (carrier, driver) pair from the available carriers.

        Selects a random carrier from the carriers list, then selects a random
        driver from that carrier's drivers. This method is used by LoadCreationFactory
        to assign a carrier and driver to a load.

        Returns:
            A tuple of (Carrier, Driver) where the driver belongs to the carrier.

        Raises:
            IndexError: If carriers list is empty.
            ValueError: If the selected carrier has no drivers (should not happen
                       with createDrivers() implementation).
        """
        if not self.carriers:
            raise IndexError("No carriers available. Create carriers first.")

        # Select a random carrier
        carrier = random.choice(self.carriers)

        # Get the drivers for this carrier
        drivers = list(carrier.drivers.all())

        if not drivers:
            raise ValueError(f"Carrier {carrier} has no drivers assigned.")

        # Select a random driver from this carrier
        driver = random.choice(drivers)

        return (carrier, driver)

    def get_compliant_carrier_driver_pair(
        self, pickup_datetime: datetime
    ) -> CarrierDriverPair:
        """
        Return a (carrier, driver) pair that satisfies HOS constraints.

        Shuffles carriers and their drivers, returning the first pair whose
        pickup would keep the driver's daily span within the effective window.
        Records the pickup on success.

        Args:
            pickup_datetime: The proposed pickup datetime.

        Returns:
            A tuple of (Carrier, Driver) that is HOS-compliant.

        Raises:
            HOSComplianceError: If no carrier/driver pair can satisfy the constraint.
        """
        if self._schedule_tracker is None:
            raise RuntimeError(
                "Cannot call get_compliant_carrier_driver_pair without enforce_hos=True"
            )

        shuffled_carriers = list(self.carriers)
        random.shuffle(shuffled_carriers)

        for carrier in shuffled_carriers:
            drivers = list(carrier.drivers.all())
            random.shuffle(drivers)
            for driver in drivers:
                if self._schedule_tracker.is_compliant(driver.pk, pickup_datetime):
                    self._schedule_tracker.record_pickup(driver.pk, pickup_datetime)
                    return (carrier, driver)

        raise HOSComplianceError(
            f"No carrier/driver pair available that satisfies HOS constraints "
            f"for pickup at {pickup_datetime}"
        )
