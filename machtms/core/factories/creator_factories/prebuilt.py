"""
Prebuilt module for batch load creation.

This module provides convenience functions for creating multiple loads
with all associated objects (customers, legs, stops, assignments).
It's designed for quick test data generation and simulation purposes.

Example usage:
    # Quick way to create 10 test loads
    from machtms.core.factories.creator_factories.prebuilt import quick_create
    results = quick_create(10)

    # Advanced usage with specific pool sizes
    from machtms.core.factories.creator_factories.prebuilt import create_batch_loads
    results = create_batch_loads(
        load_count=50,
        address_pool_size=100,
        carrier_count=20,
        stops_per_load=3
    )
"""

from typing import List

from django.db import transaction

from machtms.core.factories.creator_factories.load_creation import LoadCreationResult


def _validate_batch_parameters(
    load_count: int,
    address_pool_size: int,
    carrier_count: int,
    stops_per_load: int,
    create_legs: bool = True,
) -> None:
    """
    Validate parameters for batch load creation.

    Args:
        load_count: Number of loads to create
        address_pool_size: Size of the address pool
        carrier_count: Number of carriers to create
        stops_per_load: Number of stops per load
        create_legs: Whether legs/stops/assignments will be created.
                    When False, address_pool_size and carrier_count validation is skipped.

    Raises:
        ValueError: If any parameter is invalid
    """
    if load_count < 1:
        raise ValueError(f"load_count must be >= 1, got {load_count}")

    if create_legs:
        if address_pool_size < 1:
            raise ValueError(f"address_pool_size must be >= 1, got {address_pool_size}")
        if carrier_count < 1:
            raise ValueError(f"carrier_count must be >= 1, got {carrier_count}")
        if stops_per_load not in (2, 3):
            raise ValueError(f"stops_per_load must be 2 or 3, got {stops_per_load}")

        minimum_addresses_required = load_count * stops_per_load
        if address_pool_size < minimum_addresses_required:
            raise ValueError(
                f"address_pool_size ({address_pool_size}) is too small. "
                f"Need at least {minimum_addresses_required} addresses for "
                f"{load_count} loads with {stops_per_load} stops each."
            )


def _import_creator_classes() -> tuple:
    """
    Import FakeAddressCreator and FakeCarrierCreator classes.

    Returns:
        Tuple of (FakeAddressCreator, FakeCarrierCreator) classes

    Raises:
        ImportError: If the creator classes are not available
    """
    try:
        from machtms.core.factories.creator_factories.fake_address_creator import FakeAddressCreator
        from machtms.core.factories.creator_factories.fake_carrier_creator import FakeCarrierCreator

        return FakeAddressCreator, FakeCarrierCreator
    except ImportError as error:
        raise ImportError(
            "FakeAddressCreator and FakeCarrierCreator are required. "
            "Ensure Developer 1 has implemented these classes. "
            f"Original error: {error}"
        ) from error


def create_batch_loads(
    load_count: int,
    address_pool_size: int = 0,
    carrier_count: int = 0,
    stops_per_load: int = 2,
    create_legs: bool = True,
) -> List[LoadCreationResult]:
    """
    Create multiple complete loads with all associated objects.

    This function initializes address and carrier pools, then creates
    the specified number of loads. Each load includes:
    - A customer with address
    - The load itself
    - A leg with stops (only if create_legs=True)
    - A shipment assignment with carrier/driver (only if create_legs=True)

    Args:
        load_count: Number of loads to create
        address_pool_size: Size of the address pool for FakeAddressCreator.
                          Required when create_legs=True.
        carrier_count: Number of carriers to create in FakeCarrierCreator.
                      Required when create_legs=True.
        stops_per_load: Number of stops per load (2 or 3, default 2)
        create_legs: Whether to create legs, stops, and assignments.
                    When False, only customers and loads are created.
                    Default is True for backward compatibility.

    Returns:
        List[LoadCreationResult]: List of dictionaries, each containing:
            - 'customer': Customer instance
            - 'load': Load instance
            - 'leg': Leg instance or None (if create_legs=False)
            - 'stops': List of Stop instances or empty list (if create_legs=False)
            - 'assignment': ShipmentAssignment instance or None (if create_legs=False)

    Raises:
        ValueError: If load_count is < 1
        ValueError: If create_legs=True and address_pool_size or carrier_count is < 1
        ValueError: If create_legs=True and stops_per_load is not 2 or 3
        ImportError: If create_legs=True and FakeAddressCreator or FakeCarrierCreator are not available

    Example:
        # Full load creation with legs
        results = create_batch_loads(
            load_count=10,
            address_pool_size=30,
            carrier_count=5,
            stops_per_load=2
        )
        print(f"Created {len(results)} loads")
        for result in results:
            print(f"  Load {result['load'].reference_number}: "
                  f"{len(result['stops'])} stops")

        # Load creation without legs
        results = create_batch_loads(load_count=10, create_legs=False)
        print(f"Created {len(results)} loads without legs")
    """
    _validate_batch_parameters(
        load_count, address_pool_size, carrier_count, stops_per_load, create_legs
    )

    from machtms.core.factories.creator_factories.load_creation import LoadCreationFactory

    address_creator = None
    carrier_creator = None

    if create_legs:
        FakeAddressCreator, FakeCarrierCreator = _import_creator_classes()
        address_creator = FakeAddressCreator(address_pool_size)
        carrier_creator = FakeCarrierCreator(carrier_count)

    results: List[LoadCreationResult] = []

    with transaction.atomic():
        for _ in range(load_count):
            factory = LoadCreationFactory(
                stop_length=stops_per_load if create_legs else None,
                carrier_factory=carrier_creator,
                address_factory=address_creator,
                create_legs=create_legs,
            )
            result = factory.create_complete_load()
            results.append(result)

    return results


def quick_create(
    num_loads: int = 10,
    create_legs: bool = True,
) -> List[LoadCreationResult]:
    """
    Convenience function for quickly creating test loads.

    Provides sensible defaults for address and carrier pool sizes:
    - address_pool_size = num_loads * 3 (ensures enough unique addresses)
    - carrier_count = max(5, num_loads // 2) (reasonable carrier diversity)
    - stops_per_load = 2 (standard pickup/delivery)

    This is designed for quick testing and data seeding scenarios
    where you don't need fine-grained control over pool sizes.

    Args:
        num_loads: Number of loads to create (default: 10)
        create_legs: Whether to create legs, stops, and assignments.
                    When False, only customers and loads are created.
                    Default is True for backward compatibility.

    Returns:
        List[LoadCreationResult]: List of created load data dictionaries

    Example:
        # Create 10 loads with sensible defaults
        results = quick_create()

        # Create 50 loads
        results = quick_create(50)

        # Create loads without legs
        results = quick_create(20, create_legs=False)

        # Access created data
        for result in results:
            print(f"Load: {result['load'].reference_number}")
            print(f"  Customer: {result['customer'].customer_name}")
            if result['assignment']:
                print(f"  Carrier: {result['assignment'].carrier.carrier_name}")
    """
    if num_loads < 1:
        raise ValueError(f"num_loads must be >= 1, got {num_loads}")

    if create_legs:
        address_pool_size = num_loads * 3
        carrier_count = max(5, num_loads // 2)
        stops_per_load = 2
    else:
        address_pool_size = 0
        carrier_count = 0
        stops_per_load = 2

    results = create_batch_loads(
        load_count=num_loads,
        address_pool_size=address_pool_size,
        carrier_count=carrier_count,
        stops_per_load=stops_per_load,
        create_legs=create_legs,
    )

    total_stops = sum(len(result["stops"]) for result in results)
    print(f"Created {num_loads} loads with {total_stops} stops")

    return results
