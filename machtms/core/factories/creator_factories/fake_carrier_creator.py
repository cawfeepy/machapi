"""
FakeCarrierCreator module for generating carriers with their drivers for load simulation.

This module provides the FakeCarrierCreator class that generates Carrier instances
along with associated Driver instances for use in load creation scenarios.
"""
import random
from typing import List, Tuple, TypeAlias

from machtms.backend.carriers.models import Carrier, Driver
from machtms.core.factories.carrier import CarrierFactory, DriverFactory

# Type aliases for clarity
CarrierList: TypeAlias = List[Carrier]
CarrierDriverPair: TypeAlias = Tuple[Carrier, Driver]


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

    def __init__(self, carriers_length: int) -> None:
        """
        Initialize FakeCarrierCreator and create the specified number of carriers.

        Creates carriers_length number of carriers, each with 2-3 drivers.

        Args:
            carriers_length: Number of carriers to create. Must be >= 1.

        Raises:
            ValueError: If carriers_length is less than 1.
        """
        if carriers_length < 1:
            raise ValueError("carriers_length must be at least 1")

        self.carriers: CarrierList = []

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

        # Determine random number of drivers (2 or 3)
        num_drivers = random.randint(2, 3)

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
