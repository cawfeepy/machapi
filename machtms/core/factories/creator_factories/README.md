# Creator Factories Module

## Overview

The `creator_factories` module provides a comprehensive suite of factory classes for generating simulated transportation management data. This module is designed to support testing, development, and demo environments by creating realistic, interconnected data structures including loads, carriers, drivers, addresses, and stops.

### Module Purpose

- **Test Data Generation**: Create complete load hierarchies for unit and integration testing
- **Demo Environment Seeding**: Populate development databases with realistic sample data
- **Simulation**: Generate varied route configurations for load planning simulations
- **Rapid Prototyping**: Quickly create data structures without manual database population

### Architecture

The module follows a composition-based architecture where specialized creator classes work together:

```
                    +-------------------+
                    |   quick_create    |
                    | create_batch_loads|
                    +--------+----------+
                             |
                             v
                  +----------+-----------+
                  | LoadCreationFactory  |
                  +----------+-----------+
                             |
         +-------------------+-------------------+
         |                   |                   |
         v                   v                   v
+--------+-------+  +--------+--------+  +-------+-------+
|FakeAddressCreator||FakeCarrierCreator||FakeStopCreator|
+----------------+  +-----------------+  +---------------+
         |                   |                   |
         v                   v                   v
   AddressFactory      CarrierFactory       StopFactory
                       DriverFactory
```

---

## Module Exports

The module exposes the following public API through `__init__.py`:

```python
from machtms.core.factories.creator_factories import (
    FakeAddressCreator,
    FakeCarrierCreator,
    FakeStopCreator,
    LoadCreationFactory,
    LoadCreationResult,
    create_batch_loads,
    quick_create,
)
```

| Export | Type | Description |
|--------|------|-------------|
| `FakeAddressCreator` | Class | Generates address pools organized as route tuples |
| `FakeCarrierCreator` | Class | Generates carriers with associated drivers |
| `FakeStopCreator` | Class | Generates stops for existing legs |
| `LoadCreationFactory` | Class | Orchestrates complete load creation workflow |
| `LoadCreationResult` | TypedDict | Type definition for load creation results |
| `create_batch_loads` | Function | Creates multiple loads with configurable pools |
| `quick_create` | Function | Convenience function with sensible defaults |

---

## Dependencies

### Internal Dependencies

| Module | Import Path | Purpose |
|--------|-------------|---------|
| `AddressFactory` | `machtms.core.factories.addresses` | Creates individual Address instances |
| `CarrierFactory` | `machtms.core.factories.carrier` | Creates Carrier instances |
| `DriverFactory` | `machtms.core.factories.carrier` | Creates Driver instances |
| `CustomerFactory` | `machtms.core.factories.customer` | Creates Customer instances |
| `LoadFactory` | `machtms.core.factories.loads` | Creates Load instances |
| `LegFactory` | `machtms.core.factories.leg` | Creates Leg instances |
| `ShipmentAssignmentFactory` | `machtms.core.factories.leg` | Creates ShipmentAssignment instances |
| `StopFactory` | `machtms.core.factories.routes` | Creates Stop instances |

### External Dependencies

| Package | Usage |
|---------|-------|
| `django.db.transaction` | Atomic database operations |
| `django.utils.timezone` | Timezone-aware datetime handling |
| `random` | Random selection for variety in generated data |
| `typing` | Type hints and protocols |

---

## Class Documentation

### FakeAddressCreator

**File**: `fake_address_creator.py`

**Purpose**: Generates and organizes fake addresses into route tuples suitable for load simulation.

#### Type Aliases

```python
AddressTuple: TypeAlias = Tuple[Address, ...]
TwoStopRoute: TypeAlias = Tuple[Address, Address]
ThreeStopRoute: TypeAlias = Tuple[Address, Address, Address]
AddressList: TypeAlias = List[Address]
```

#### Class Definition

```python
class FakeAddressCreator:
    """
    Creates and organizes fake addresses for load simulation purposes.
    """

    fakeAddresses: List[AddressTuple]  # List of 2-tuple or 3-tuple routes
```

#### Constructor

```python
def __init__(self, N: int) -> None
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `N` | `int` | Total number of addresses to create. Must be >= 3 |

**Raises**: `ValueError` if N < 3

**Behavior**:
1. Creates N addresses using `AddressFactory.create()`
2. Designates the first address (index 0) as "shipper-only" (cannot be a receiver)
3. Generates approximately N/2 address tuples, alternating between 2-tuples and 3-tuples

#### Methods

##### `filterFakeAddresses`

```python
def filterFakeAddresses(self, stop_length: int) -> List[AddressTuple]
```

Filters address tuples by the specified length.

| Parameter | Type | Description |
|-----------|------|-------------|
| `stop_length` | `int` | Desired tuple length (2 or 3) |

**Returns**: List of address tuples matching the specified length. Returns empty list if `stop_length` is not 2 or 3.

##### `get_address_tuple`

```python
def get_address_tuple(self) -> AddressTuple
```

Returns a random address tuple from the pool.

**Returns**: A tuple containing 2 or 3 `Address` instances.

**Raises**: `IndexError` if `fakeAddresses` is empty.

#### Usage Example

```python
from machtms.core.factories.creator_factories import FakeAddressCreator

# Create a pool of 10 addresses organized into tuples
address_creator = FakeAddressCreator(N=10)

# Get all 2-stop routes
two_stop_routes = address_creator.filterFakeAddresses(stop_length=2)
for route in two_stop_routes:
    shipper, receiver = route
    print(f"Route: {shipper.city} -> {receiver.city}")

# Get all 3-stop routes
three_stop_routes = address_creator.filterFakeAddresses(stop_length=3)
for route in three_stop_routes:
    shipper, stop, receiver = route
    print(f"Route: {shipper.city} -> {stop.city} -> {receiver.city}")

# Get a random route tuple for load creation
random_route = address_creator.get_address_tuple()
```

#### Business Rules

> **Important Constraint**: The first address created (PK=1, index 0) can only appear as a shipper (first position in a tuple). It cannot appear as a receiver (last position). This enforces the business rule that certain locations are pickup-only.

---

### FakeCarrierCreator

**File**: `fake_carrier_creator.py`

**Purpose**: Generates carriers with their associated drivers for load assignment.

#### Type Aliases

```python
CarrierList: TypeAlias = List[Carrier]
CarrierDriverPair: TypeAlias = Tuple[Carrier, Driver]
```

#### Class Definition

```python
class FakeCarrierCreator:
    """
    Creates and manages fake carriers with their drivers for load simulation.
    """

    carriers: CarrierList  # List of Carrier instances
```

#### Constructor

```python
def __init__(self, carriers_length: int) -> None
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `carriers_length` | `int` | Number of carriers to create. Must be >= 1 |

**Raises**: `ValueError` if `carriers_length` < 1

**Behavior**: Creates the specified number of carriers, each with 2-3 randomly assigned drivers.

#### Methods

##### `createDrivers`

```python
def createDrivers(self) -> Carrier
```

Creates a new carrier with 2-3 associated drivers.

**Returns**: The newly created `Carrier` instance.

**Side Effects**:
- Creates one `Carrier` in the database
- Creates 2-3 `Driver` instances associated with the carrier
- Appends the carrier to `self.carriers`

##### `get_carrier_driver_pair`

```python
def get_carrier_driver_pair(self) -> CarrierDriverPair
```

Returns a random carrier and one of its drivers.

**Returns**: Tuple of `(Carrier, Driver)` where the driver belongs to the carrier.

**Raises**:
- `IndexError` if no carriers are available
- `ValueError` if the selected carrier has no drivers

#### Usage Example

```python
from machtms.core.factories.creator_factories import FakeCarrierCreator

# Create 5 carriers, each with 2-3 drivers
carrier_creator = FakeCarrierCreator(carriers_length=5)

# Access all carriers
print(f"Created {len(carrier_creator.carriers)} carriers")
for carrier in carrier_creator.carriers:
    driver_count = carrier.drivers.count()
    print(f"  {carrier.carrier_name}: {driver_count} drivers")

# Get a random carrier/driver pair for assignment
carrier, driver = carrier_creator.get_carrier_driver_pair()
print(f"Assigned: {driver.first_name} from {carrier.carrier_name}")
```

---

### FakeStopCreator

**File**: `fake_stop_creator.py`

**Purpose**: Generates stops for existing legs with proper sequencing, actions, and time ranges.

#### Type Aliases

```python
StopList: TypeAlias = List[Stop]
```

#### Class Constants

```python
FIRST_STOP_ACTIONS: List[str] = ["LL", "HL"]    # Live Load, Hook Loaded
MIDDLE_STOP_ACTIONS: List[str] = ["HUBP", "HUBD"]  # Hub Pickup, Hub Delivery
LAST_STOP_ACTIONS: List[str] = ["LU", "LD"]     # Live Unload, Drop Loaded
```

#### Class Definition

```python
class FakeStopCreator:
    """
    Creates and manages fake stops for legs in test scenarios.
    """

    stops: StopList  # All stops created by this instance
```

#### Constructor

```python
def __init__(self) -> None
```

Initializes the creator with an empty stops list.

#### Methods

##### `create_stops_for_leg`

```python
def create_stops_for_leg(
    self,
    leg: Leg,
    num_stops: int = 2,
    base_date: Optional[datetime] = None,
) -> StopList
```

Creates stops for a given leg with proper sequencing.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `leg` | `Leg` | - | Leg instance to associate stops with |
| `num_stops` | `int` | 2 | Number of stops to create (2 or 3) |
| `base_date` | `datetime` | None | Starting datetime for time ranges |

**Returns**: List of created `Stop` instances ordered by `stop_number`.

**Raises**: `ValueError` if `num_stops` is not 2 or 3.

**Behavior**:
- Stop numbers start at 1
- Actions are assigned based on position (first=pickup, last=delivery, middle=hub)
- Time ranges are spaced 4 hours apart with 2-hour windows
- If `base_date` is None, uses current time + 1-7 random days

##### `create_batch_stops`

```python
def create_batch_stops(
    self,
    legs: List[Leg],
    stops_per_leg: int = 2,
) -> List[StopList]
```

Creates stops for multiple legs at once.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `legs` | `List[Leg]` | - | Leg instances to create stops for |
| `stops_per_leg` | `int` | 2 | Number of stops per leg (2 or 3) |

**Returns**: List of stop lists, one for each leg.

##### `get_all_stops`

```python
def get_all_stops(self) -> StopList
```

Returns all stops created by this instance.

##### `get_stop_count`

```python
def get_stop_count(self) -> int
```

Returns the total number of stops created.

#### Usage Example

```python
from machtms.core.factories.creator_factories import FakeStopCreator
from machtms.core.factories.leg import LegFactory

# Create a leg first
leg = LegFactory.create()

# Create stops for the leg
creator = FakeStopCreator()
stops = creator.create_stops_for_leg(leg, num_stops=3)

for stop in stops:
    print(f"Stop {stop.stop_number}: {stop.action} at {stop.address.city}")
    print(f"  Window: {stop.start_range} - {stop.end_range}")

# Batch creation for multiple legs
legs = [LegFactory.create() for _ in range(5)]
all_stops = creator.create_batch_stops(legs, stops_per_leg=2)

print(f"Total stops created: {creator.get_stop_count()}")
```

#### Stop Action Codes

| Code | Description | Position |
|------|-------------|----------|
| `LL` | Live Load | First stop |
| `HL` | Hook Loaded | First stop |
| `HUBP` | Hub Pickup | Middle stop |
| `HUBD` | Hub Delivery | Middle stop |
| `LU` | Live Unload | Last stop |
| `LD` | Drop Loaded | Last stop |

---

### LoadCreationFactory

**File**: `load_creation.py`

**Purpose**: Orchestrates the complete load creation workflow, coordinating all other factories to build a full load hierarchy.

#### Protocols

The factory uses Python protocols to define expected interfaces:

```python
class CarrierFactoryProtocol(Protocol):
    def get_carrier_driver_pair(self) -> Tuple[Carrier, Driver]: ...

class AddressFactoryProtocol(Protocol):
    def get_address_tuple(self) -> Tuple[Address, ...]: ...
```

#### Result Type

```python
class LoadCreationResult(TypedDict):
    customer: Customer
    load: Load
    leg: Leg
    stops: List[Stop]
    assignment: ShipmentAssignment
```

#### Class Constants

```python
FIRST_STOP_ACTIONS: List[str] = ["LL", "HL"]
MIDDLE_STOP_ACTIONS: List[str] = ["HUBP", "HUBD"]
LAST_STOP_ACTIONS: List[str] = ["LU", "LD"]
```

#### Constructor

```python
def __init__(
    self,
    stop_length: int,
    carrier_factory: CarrierFactoryProtocol,
    address_factory: AddressFactoryProtocol,
) -> None
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `stop_length` | `int` | Number of stops per leg (2 or 3) |
| `carrier_factory` | `CarrierFactoryProtocol` | Factory providing carrier/driver pairs |
| `address_factory` | `AddressFactoryProtocol` | Factory providing address tuples |

**Raises**: `ValueError` if `stop_length` is not 2 or 3, or if factories are None.

#### Methods

##### `create_customer`

```python
def create_customer(self) -> Customer
```

Creates a customer with an associated address using `CustomerFactory`.

**Returns**: Saved `Customer` instance with address.

##### `create_load`

```python
def create_load(self, customer: Customer) -> Load
```

Creates a load associated with the given customer.

| Parameter | Type | Description |
|-----------|------|-------------|
| `customer` | `Customer` | Customer to associate with the load |

**Returns**: Saved `Load` instance with:
- Auto-generated `reference_number` and `bol_number`
- Status: `LoadStatus.PENDING`
- Billing status: `BillingStatus.PENDING_DELIVERY`
- Randomly selected `trailer_type`

##### `create_leg`

```python
def create_leg(self, load: Load) -> Leg
```

Creates a leg associated with the given load.

**Returns**: Saved `Leg` instance.

##### `create_stops`

```python
def create_stops(self, leg: Leg) -> List[Stop]
```

Creates stops for the leg using addresses from the address factory.

**Returns**: List of `Stop` instances ordered by `stop_number`.

##### `assign_carrier_driver`

```python
def assign_carrier_driver(self, leg: Leg) -> ShipmentAssignment
```

Creates a shipment assignment linking a carrier/driver to the leg.

**Returns**: Saved `ShipmentAssignment` instance.

##### `create_complete_load`

```python
@transaction.atomic
def create_complete_load(self) -> LoadCreationResult
```

Orchestrates the complete load creation workflow within a database transaction.

**Returns**: `LoadCreationResult` dictionary containing all created objects.

**Transaction Behavior**: The entire operation is wrapped in `transaction.atomic()`. If any step fails, all changes are rolled back.

#### Pipeline Position

```
Request Flow:
1. create_customer()     -> Customer + Address
2. create_load()         -> Load (links to Customer)
3. create_leg()          -> Leg (links to Load)
4. create_stops()        -> Stops (link to Leg, use Address pool)
5. assign_carrier_driver() -> ShipmentAssignment (links Carrier+Driver to Leg)
```

#### Usage Example

```python
from machtms.core.factories.creator_factories import (
    FakeAddressCreator,
    FakeCarrierCreator,
    LoadCreationFactory,
)

# Initialize the creator factories
address_creator = FakeAddressCreator(N=20)
carrier_creator = FakeCarrierCreator(carriers_length=5)

# Create the load factory
factory = LoadCreationFactory(
    stop_length=2,
    carrier_factory=carrier_creator,
    address_factory=address_creator,
)

# Create a complete load
result = factory.create_complete_load()

# Access created objects
print(f"Customer: {result['customer'].customer_name}")
print(f"Load: {result['load'].reference_number}")
print(f"Leg ID: {result['leg'].id}")
print(f"Stops: {len(result['stops'])}")
print(f"Carrier: {result['assignment'].carrier.carrier_name}")
print(f"Driver: {result['assignment'].driver.first_name}")
```

---

## Convenience Functions

### create_batch_loads

**File**: `prebuilt.py`

Creates multiple complete loads with configurable pool sizes.

```python
def create_batch_loads(
    load_count: int,
    address_pool_size: int,
    carrier_count: int,
    stops_per_load: int = 2,
) -> List[LoadCreationResult]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `load_count` | `int` | - | Number of loads to create |
| `address_pool_size` | `int` | - | Size of the address pool |
| `carrier_count` | `int` | - | Number of carriers to create |
| `stops_per_load` | `int` | 2 | Number of stops per load (2 or 3) |

**Returns**: List of `LoadCreationResult` dictionaries.

**Raises**:
- `ValueError` if any count parameter is < 1
- `ValueError` if `stops_per_load` is not 2 or 3
- `ValueError` if `address_pool_size` < `load_count * stops_per_load`

#### Validation Rules

The function validates that the address pool is large enough:

```python
minimum_addresses_required = load_count * stops_per_load
if address_pool_size < minimum_addresses_required:
    raise ValueError(...)
```

#### Usage Example

```python
from machtms.core.factories.creator_factories import create_batch_loads

# Create 50 loads with 3-stop routes
results = create_batch_loads(
    load_count=50,
    address_pool_size=200,
    carrier_count=20,
    stops_per_load=3,
)

print(f"Created {len(results)} loads")

# Process results
for result in results:
    load = result['load']
    stops = result['stops']
    assignment = result['assignment']

    print(f"Load {load.reference_number}:")
    print(f"  Customer: {result['customer'].customer_name}")
    print(f"  Stops: {len(stops)}")
    print(f"  Carrier: {assignment.carrier.carrier_name}")
```

---

### quick_create

**File**: `prebuilt.py`

Convenience function for quickly creating test loads with sensible defaults.

```python
def quick_create(num_loads: int = 10) -> List[LoadCreationResult]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_loads` | `int` | 10 | Number of loads to create |

**Returns**: List of `LoadCreationResult` dictionaries.

**Raises**: `ValueError` if `num_loads` < 1.

#### Default Calculations

```python
address_pool_size = num_loads * 3      # Ensures enough unique addresses
carrier_count = max(5, num_loads // 2)  # Reasonable carrier diversity
stops_per_load = 2                      # Standard pickup/delivery
```

#### Usage Example

```python
from machtms.core.factories.creator_factories import quick_create

# Create 10 loads with defaults (prints summary)
results = quick_create()
# Output: Created 10 loads with 20 stops

# Create 100 loads
results = quick_create(100)
# Output: Created 100 loads with 200 stops

# Access specific data
for result in results:
    print(f"Load: {result['load'].reference_number}")
    print(f"  Customer: {result['customer'].customer_name}")
    print(f"  Carrier: {result['assignment'].carrier.carrier_name}")
```

---

## Complete Workflow Example

The following example demonstrates the full workflow from initialization to load creation:

```python
from machtms.core.factories.creator_factories import (
    FakeAddressCreator,
    FakeCarrierCreator,
    LoadCreationFactory,
    quick_create,
    create_batch_loads,
)

# Method 1: Quick creation with sensible defaults
results = quick_create(10)

# Method 2: Batch creation with custom configuration
results = create_batch_loads(
    load_count=25,
    address_pool_size=100,
    carrier_count=10,
    stops_per_load=3,
)

# Method 3: Manual factory orchestration for fine-grained control
address_creator = FakeAddressCreator(N=50)
carrier_creator = FakeCarrierCreator(carriers_length=10)

# Create multiple loads with different configurations
two_stop_factory = LoadCreationFactory(
    stop_length=2,
    carrier_factory=carrier_creator,
    address_factory=address_creator,
)

three_stop_factory = LoadCreationFactory(
    stop_length=3,
    carrier_factory=carrier_creator,
    address_factory=address_creator,
)

# Create 5 two-stop loads and 5 three-stop loads
two_stop_results = [two_stop_factory.create_complete_load() for _ in range(5)]
three_stop_results = [three_stop_factory.create_complete_load() for _ in range(5)]

print(f"Created {len(two_stop_results)} two-stop loads")
print(f"Created {len(three_stop_results)} three-stop loads")
```

---

## Testing Integration

### Using with pytest

```python
import pytest
from machtms.core.factories.creator_factories import (
    FakeAddressCreator,
    FakeCarrierCreator,
    FakeStopCreator,
    LoadCreationFactory,
    quick_create,
)


@pytest.fixture
def address_pool():
    """Create an address pool for tests."""
    return FakeAddressCreator(N=20)


@pytest.fixture
def carrier_pool():
    """Create a carrier pool for tests."""
    return FakeCarrierCreator(carriers_length=5)


@pytest.fixture
def load_factory(address_pool, carrier_pool):
    """Create a configured LoadCreationFactory."""
    return LoadCreationFactory(
        stop_length=2,
        carrier_factory=carrier_pool,
        address_factory=address_pool,
    )


@pytest.mark.django_db
class TestLoadCreation:

    def test_create_complete_load(self, load_factory):
        result = load_factory.create_complete_load()

        assert result['customer'] is not None
        assert result['load'] is not None
        assert result['leg'] is not None
        assert len(result['stops']) == 2
        assert result['assignment'] is not None

    def test_quick_create(self):
        results = quick_create(5)

        assert len(results) == 5
        for result in results:
            assert 'load' in result
            assert 'customer' in result
            assert 'stops' in result


@pytest.mark.django_db
class TestFakeStopCreator:

    def test_create_stops_for_leg(self, load_factory):
        result = load_factory.create_complete_load()
        leg = result['leg']

        stop_creator = FakeStopCreator()
        stops = stop_creator.create_stops_for_leg(leg, num_stops=3)

        assert len(stops) == 3
        assert stops[0].action in ["LL", "HL"]  # First stop
        assert stops[2].action in ["LU", "LD"]  # Last stop
```

---

## Error Handling

### Common Exceptions

| Exception | Cause | Solution |
|-----------|-------|----------|
| `ValueError("N must be at least 3...")` | `FakeAddressCreator(N=2)` | Use N >= 3 |
| `ValueError("carriers_length must be at least 1")` | `FakeCarrierCreator(carriers_length=0)` | Use carriers_length >= 1 |
| `ValueError("stop_length must be 2 or 3...")` | Invalid stop_length | Use 2 or 3 |
| `ValueError("address_pool_size is too small...")` | Pool too small for load count | Increase address_pool_size |
| `IndexError("No carriers available...")` | Empty carrier list | Create carriers first |

### Transaction Safety

All batch operations are wrapped in `transaction.atomic()`:

```python
with transaction.atomic():
    # All load creations happen here
    # If any fails, all are rolled back
```

---

## Performance Considerations

### Memory Usage

- Address and carrier pools are kept in memory
- For large batch operations (1000+ loads), consider chunking

### Database Operations

- Each `create_complete_load()` creates approximately:
  - 1 Customer + 1 Address (customer's)
  - 1 Load
  - 1 Leg
  - 2-3 Stops
  - 1 ShipmentAssignment

- For 100 loads with 2 stops each: ~600 database inserts

### Recommendations

```python
# For small test cases (< 50 loads)
results = quick_create(20)

# For larger datasets, use create_batch_loads with appropriate pool sizes
results = create_batch_loads(
    load_count=500,
    address_pool_size=1000,  # 2x load count for variety
    carrier_count=50,        # 10% of load count
    stops_per_load=2,
)
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-01 | Initial implementation |

---

## Related Documentation

- [Factory Boy Documentation](https://factoryboy.readthedocs.io/)
- [Django REST Framework Testing](https://www.django-rest-framework.org/api-guide/testing/)
- [Django Database Transactions](https://docs.djangoproject.com/en/stable/topics/db/transactions/)
