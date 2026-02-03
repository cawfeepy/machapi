# FakeCarrierCreator Module (`fake_carrier_creator.py`)

## File Overview

The `fake_carrier_creator.py` module provides the `FakeCarrierCreator` class, which generates carriers along with their associated drivers for load simulation purposes. Each carrier is created with 2-3 drivers, establishing the carrier-driver relationships needed for shipment assignments.

### Purpose

In a transportation management system, loads are assigned to carriers who employ drivers. This class creates a pool of carriers, each with multiple drivers, that can be randomly selected when creating shipment assignments. It ensures realistic data relationships where drivers belong to specific carriers.

### Role in Application Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Load Creation Pipeline                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  FakeAddressCreator ──┐                                     │
│  (Address Pool)       │                                     │
│                       ├──► LoadCreationFactory              │
│  FakeCarrierCreator ──┘         │                           │
│  (Carrier Pool)                 │                           │
│       │                         ▼                           │
│       │                   ShipmentAssignment                │
│       │                         │                           │
│       └─────────────────────────┘                           │
│         get_carrier_driver_pair()                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Type Aliases

| Type Alias | Definition | Description |
|------------|------------|-------------|
| `CarrierList` | `List[Carrier]` | List of Carrier instances |
| `CarrierDriverPair` | `Tuple[Carrier, Driver]` | A carrier with one of its drivers |

---

## Class: FakeCarrierCreator

### Description

Creates and manages fake carriers with their drivers for load simulation. This class generates `Carrier` instances using `CarrierFactory`, each with 2-3 randomly assigned drivers created via `DriverFactory`. The carriers are stored in a list for easy access by `LoadCreationFactory`.

### Class Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `carriers` | `CarrierList` | List of Carrier instances, each with 2-3 associated drivers |

---

## Methods

### `__init__(self, carriers_length: int) -> None`

Initializes FakeCarrierCreator and creates the specified number of carriers.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `carriers_length` | `int` | Yes | Number of carriers to create. Must be >= 1 |

#### Raises

| Exception | Condition |
|-----------|-----------|
| `ValueError` | If carriers_length is less than 1 |

#### Behavior

1. Validates that carriers_length >= 1
2. Initializes empty carriers list
3. Calls `createDrivers()` for each carrier to be created

#### Usage Example

```python
from machtms.core.factories.creator_factories import FakeCarrierCreator

# Create 5 carriers, each with 2-3 drivers
carrier_creator = FakeCarrierCreator(carriers_length=5)

print(f"Created {len(carrier_creator.carriers)} carriers")
```

---

### `createDrivers(self) -> Carrier`

Creates a carrier with 2-3 randomly assigned drivers.

#### Returns

| Type | Description |
|------|-------------|
| `Carrier` | The newly created Carrier instance with its associated drivers |

#### Behavior

1. Creates a new Carrier using `CarrierFactory.create()`
2. Determines a random number of drivers (2 or 3)
3. Creates that many Driver instances using `DriverFactory.create(carrier=carrier)`
4. Appends the carrier to `self.carriers` list
5. Returns the carrier

#### Side Effects

- Creates one Carrier record in the database
- Creates 2-3 Driver records in the database, linked to the carrier
- Appends carrier to `self.carriers` list

#### Usage Example

```python
carrier_creator = FakeCarrierCreator(carriers_length=1)

# Add another carrier on demand
new_carrier = carrier_creator.createDrivers()
print(f"Created carrier: {new_carrier.carrier_name}")
print(f"Drivers: {list(new_carrier.drivers.all())}")
```

---

### `get_carrier_driver_pair(self) -> CarrierDriverPair`

Returns a random (carrier, driver) pair from the available carriers.

#### Returns

| Type | Description |
|------|-------------|
| `CarrierDriverPair` | A tuple of (Carrier, Driver) where the driver belongs to the carrier |

#### Raises

| Exception | Condition |
|-----------|-----------|
| `IndexError` | If carriers list is empty |
| `ValueError` | If the selected carrier has no drivers (should not happen normally) |

#### Behavior

1. Validates that carriers list is not empty
2. Selects a random carrier from the list
3. Retrieves all drivers for that carrier via `carrier.drivers.all()`
4. Validates that the carrier has at least one driver
5. Selects a random driver from the carrier's drivers
6. Returns the (carrier, driver) tuple

#### Pipeline Position

This method implements the `CarrierFactoryProtocol` interface expected by `LoadCreationFactory`. It is called during the shipment assignment phase of the load creation pipeline.

```
LoadCreationFactory.assign_carrier_driver()
    └──► carrier_factory.get_carrier_driver_pair()  <── This method
            └──► Returns (Carrier, Driver) for ShipmentAssignment
```

#### Usage Example

```python
carrier_creator = FakeCarrierCreator(carriers_length=10)

# Get a random carrier/driver pair for assignment
carrier, driver = carrier_creator.get_carrier_driver_pair()

print(f"Carrier: {carrier.carrier_name}")
print(f"Driver: {driver.first_name} {driver.last_name}")
print(f"Driver's carrier: {driver.carrier.carrier_name}")  # Same as carrier
```

---

## Complete Usage Example

```python
from machtms.core.factories.creator_factories import (
    FakeAddressCreator,
    FakeCarrierCreator,
    LoadCreationFactory,
)

# Step 1: Create carrier pool
carrier_creator = FakeCarrierCreator(carriers_length=10)
print(f"Created {len(carrier_creator.carriers)} carriers")

# Step 2: Inspect carriers and their drivers
for carrier in carrier_creator.carriers[:3]:
    drivers = list(carrier.drivers.all())
    print(f"Carrier: {carrier.carrier_name}")
    for driver in drivers:
        print(f"  - Driver: {driver.first_name} {driver.last_name}")

# Step 3: Get random carrier/driver pairs
for _ in range(5):
    carrier, driver = carrier_creator.get_carrier_driver_pair()
    print(f"Pair: {carrier.carrier_name} / {driver.first_name}")

# Step 4: Use with LoadCreationFactory
address_creator = FakeAddressCreator(N=20)
factory = LoadCreationFactory(
    stop_length=2,
    carrier_factory=carrier_creator,
    address_factory=address_creator,
)
result = factory.create_complete_load()

# The assignment uses a carrier/driver from our pool
print(f"Assigned carrier: {result['assignment'].carrier.carrier_name}")
print(f"Assigned driver: {result['assignment'].driver.first_name}")
```

---

## Integration with LoadCreationFactory

The `FakeCarrierCreator` class is designed to work seamlessly with `LoadCreationFactory` through the `CarrierFactoryProtocol` interface.

### Protocol Definition (from load_creation.py)

```python
class CarrierFactoryProtocol(Protocol):
    """Protocol defining the interface for carrier factories."""

    def get_carrier_driver_pair(self) -> Tuple["Carrier", "Driver"]:
        """Return a carrier and driver pair for assignment."""
        ...
```

### Integration Flow

```
┌─────────────────────────────────────────────────────────────┐
│              LoadCreationFactory Workflow                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. create_customer()                                        │
│  2. create_load(customer)                                    │
│  3. create_leg(load)                                         │
│  4. create_stops(leg)  ◄── Uses address_factory              │
│  5. assign_carrier_driver(leg)  ◄── Uses carrier_factory     │
│         │                                                    │
│         └──► carrier_factory.get_carrier_driver_pair()       │
│                    │                                         │
│                    └──► Returns (Carrier, Driver)            │
│                              │                               │
│                              └──► ShipmentAssignment created │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Dependencies

### Internal Dependencies

| Import | Purpose |
|--------|---------|
| `machtms.backend.carriers.models.Carrier` | The Carrier model |
| `machtms.backend.carriers.models.Driver` | The Driver model |
| `machtms.core.factories.carrier.CarrierFactory` | Base factory for creating Carrier instances |
| `machtms.core.factories.carrier.DriverFactory` | Base factory for creating Driver instances |

### External Dependencies

| Import | Purpose |
|--------|---------|
| `random` | For random driver count (2-3) and random selection |
| `typing.List, Tuple, TypeAlias` | Type hint definitions |

---

## Database Schema Relationship

```
┌─────────────┐       ┌─────────────┐
│   Carrier   │       │   Driver    │
├─────────────┤       ├─────────────┤
│ id          │───┐   │ id          │
│ carrier_name│   │   │ first_name  │
│ ...         │   │   │ last_name   │
└─────────────┘   │   │ carrier_id  │◄──┘ (ForeignKey)
                  │   │ ...         │
                  │   └─────────────┘
                  │
                  └──── One carrier has many drivers
```

The `FakeCarrierCreator` creates this relationship by:
1. Creating a Carrier via `CarrierFactory.create()`
2. Creating 2-3 Drivers via `DriverFactory.create(carrier=carrier)`

---

## Design Notes

1. **Pool-Based Design**: Creates a pool of carriers upfront, allowing random selection during load creation without repeated database factory calls.

2. **Realistic Data**: Each carrier has 2-3 drivers, reflecting real-world scenarios where trucking companies employ multiple drivers.

3. **Protocol Compliance**: Implements `CarrierFactoryProtocol` for seamless integration with `LoadCreationFactory`.

4. **Lazy Driver Fetching**: Uses `carrier.drivers.all()` at selection time rather than caching drivers, ensuring data consistency with the database.

5. **Random Distribution**: Random carrier selection ensures load assignments are distributed across the carrier pool, simulating realistic business scenarios.
