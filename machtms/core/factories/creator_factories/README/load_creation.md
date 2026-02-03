# LoadCreationFactory Module (`load_creation.py`)

## File Overview

The `load_creation.py` module provides the `LoadCreationFactory` class, which orchestrates the complete load creation workflow in the machTMS transportation management system. It uses composition to coordinate existing factories and creates a full load hierarchy with all associated objects.

### Purpose

Creating a complete load in a TMS involves multiple interconnected entities: customers, loads, legs, stops, carriers, drivers, and shipment assignments. This factory class encapsulates the entire workflow, ensuring proper sequencing and relationship management.

### Role in Application Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Load Creation Orchestration                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────┐    ┌─────────────────┐                    │
│   │FakeAddressCreator│    │FakeCarrierCreator│                   │
│   └────────┬────────┘    └────────┬────────┘                    │
│            │                      │                              │
│            └──────────┬───────────┘                              │
│                       │                                          │
│                       ▼                                          │
│            ┌──────────────────────┐                              │
│            │  LoadCreationFactory │                              │
│            └──────────┬───────────┘                              │
│                       │                                          │
│     ┌─────────────────┼─────────────────┐                        │
│     ▼                 ▼                 ▼                        │
│ ┌────────┐      ┌──────────┐      ┌──────────┐                   │
│ │Customer│◄─────│   Load   │◄─────│   Leg    │                   │
│ └────────┘      └──────────┘      └──────────┘                   │
│                                        │                         │
│                       ┌────────────────┼────────────────┐        │
│                       ▼                ▼                ▼        │
│                   ┌──────┐         ┌──────┐     ┌────────────┐   │
│                   │Stop 1│         │Stop 2│ ... │ Assignment │   │
│                   └──────┘         └──────┘     └────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Protocol Definitions

### CarrierFactoryProtocol

Defines the interface for carrier factories used by `LoadCreationFactory`.

```python
class CarrierFactoryProtocol(Protocol):
    def get_carrier_driver_pair(self) -> Tuple[Carrier, Driver]:
        """Return a carrier and driver pair for assignment."""
        ...
```

**Implemented by**: `FakeCarrierCreator`

### AddressFactoryProtocol

Defines the interface for address factories used by `LoadCreationFactory`.

```python
class AddressFactoryProtocol(Protocol):
    def get_address_tuple(self) -> Tuple[Address, ...]:
        """Return a tuple of addresses for stops."""
        ...
```

**Implemented by**: `FakeAddressCreator`

---

## Type Definitions

### LoadCreationResult (TypedDict)

Defines the structure of the dictionary returned by `create_complete_load()`.

| Key | Type | Description |
|-----|------|-------------|
| `customer` | `Customer` | The created customer instance |
| `load` | `Load` | The created load instance |
| `leg` | `Leg` | The created leg instance |
| `stops` | `List[Stop]` | List of created stop instances |
| `assignment` | `ShipmentAssignment` | The carrier/driver assignment |

---

## Class: LoadCreationFactory

### Description

Factory for creating complete loads with all associated objects. This class orchestrates the creation of a full load hierarchy including Customer, Load, Leg, Stops, and ShipmentAssignment.

### Class Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `FIRST_STOP_ACTIONS` | `["LL", "HL"]` | Valid actions for first stop (Live Load, Hook Loaded) |
| `MIDDLE_STOP_ACTIONS` | `["HUBP", "HUBD"]` | Valid actions for middle stops (Hub Pickup, Hub Delivery) |
| `LAST_STOP_ACTIONS` | `["LU", "LD"]` | Valid actions for last stop (Live Unload, Drop Loaded) |

### Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `stop_length` | `int` | Number of stops per leg (2 or 3) |
| `carrier_factory` | `CarrierFactoryProtocol` | Factory providing (carrier, driver) pairs |
| `address_factory` | `AddressFactoryProtocol` | Factory providing address tuples |

---

## Methods

### `__init__(self, stop_length, carrier_factory, address_factory) -> None`

Initializes LoadCreationFactory with configuration.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `stop_length` | `int` | Yes | Number of stops per leg (must be 2 or 3) |
| `carrier_factory` | `CarrierFactoryProtocol` | Yes | Object with `get_carrier_driver_pair()` method |
| `address_factory` | `AddressFactoryProtocol` | Yes | Object with `get_address_tuple()` method |

#### Raises

| Exception | Condition |
|-----------|-----------|
| `ValueError` | If stop_length is not 2 or 3 |
| `ValueError` | If carrier_factory is None |
| `ValueError` | If address_factory is None |

#### Usage Example

```python
from machtms.core.factories.creator_factories import (
    FakeAddressCreator,
    FakeCarrierCreator,
    LoadCreationFactory,
)

address_creator = FakeAddressCreator(N=20)
carrier_creator = FakeCarrierCreator(carriers_length=5)

factory = LoadCreationFactory(
    stop_length=2,
    carrier_factory=carrier_creator,
    address_factory=address_creator,
)
```

---

### `create_customer(self) -> Customer`

Creates a customer with an associated address.

#### Returns

| Type | Description |
|------|-------------|
| `Customer` | Saved Customer instance with address |

#### Behavior

Uses `CustomerFactory` which internally creates an address via `AddressFactory`. The customer gets a unique address (not from the address pool).

#### Pipeline Position

```
create_complete_load()
    └──► create_customer()  <── First step
            └──► CustomerFactory.create()
```

---

### `create_load(self, customer: Customer) -> Load`

Creates a load associated with the given customer.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `customer` | `Customer` | Yes | Customer instance to associate with the load |

#### Returns

| Type | Description |
|------|-------------|
| `Load` | Saved Load instance |

#### Behavior

Generates a load with:
- Auto-generated `reference_number` and `bol_number` (via factory sequences)
- Status: `LoadStatus.PENDING`
- Billing status: `BillingStatus.PENDING_DELIVERY`
- Randomly selected `trailer_type` from `TrailerType.choices`

#### Pipeline Position

```
create_complete_load()
    └──► create_customer()
    └──► create_load(customer)  <── Second step
            └──► LoadFactory.create(...)
```

---

### `create_leg(self, load: Load) -> Leg`

Creates a leg associated with the given load.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `load` | `Load` | Yes | Load instance to associate with the leg |

#### Returns

| Type | Description |
|------|-------------|
| `Leg` | Saved Leg instance |

#### Pipeline Position

```
create_complete_load()
    └──► create_customer()
    └──► create_load(customer)
    └──► create_leg(load)  <── Third step
            └──► LegFactory.create(load=load)
```

---

### `_determine_stop_action(self, stop_index: int, total_stops: int) -> str`

**Private Method** - Determines the appropriate action for a stop based on its position.

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `stop_index` | `int` | Zero-based index of the stop |
| `total_stops` | `int` | Total number of stops in the leg |

#### Returns

| Type | Description |
|------|-------------|
| `str` | Action code (e.g., 'LL', 'LU', 'HUBP') |

#### Logic

| Position | Actions | Meaning |
|----------|---------|---------|
| First (index 0) | `LL` or `HL` | Live Load or Hook Loaded |
| Middle | `HUBP` or `HUBD` | Hub Pickup or Hub Delivery |
| Last | `LU` or `LD` | Live Unload or Drop Loaded |

---

### `create_stops(self, leg: Leg) -> List[Stop]`

Creates stops for the given leg.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `leg` | `Leg` | Yes | Leg instance to associate stops with |

#### Returns

| Type | Description |
|------|-------------|
| `List[Stop]` | List of saved Stop instances ordered by stop_number |

#### Behavior

1. Gets addresses from `address_factory.get_address_tuple()`
2. Creates Stop instances with proper sequencing
3. Assigns actions based on position (first, middle, last)
4. Sets time windows:
   - `start_range`: now + 1-7 days (random offset)
   - `end_range`: start_range + 2 hours
   - Each subsequent stop: +4 hours from previous

#### Stop Actions by Position

| Position | Possible Actions | Description |
|----------|-----------------|-------------|
| First (stop_number=1) | `LL`, `HL` | Live Load, Hook Loaded |
| Middle (stop_number=2, only for 3-stop legs) | `HUBP`, `HUBD` | Hub Pickup, Hub Delivery |
| Last | `LU`, `LD` | Live Unload, Drop Loaded |

#### Pipeline Position

```
create_complete_load()
    └──► create_customer()
    └──► create_load(customer)
    └──► create_leg(load)
    └──► create_stops(leg)  <── Fourth step
            └──► address_factory.get_address_tuple()
            └──► Stop.objects.create(...) for each address
```

---

### `assign_carrier_driver(self, leg: Leg) -> ShipmentAssignment`

Creates a shipment assignment for the given leg.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `leg` | `Leg` | Yes | Leg instance to assign carrier/driver to |

#### Returns

| Type | Description |
|------|-------------|
| `ShipmentAssignment` | Saved ShipmentAssignment instance |

#### Behavior

1. Gets carrier/driver pair from `carrier_factory.get_carrier_driver_pair()`
2. Creates `ShipmentAssignment` linking carrier, driver, and leg

#### Pipeline Position

```
create_complete_load()
    └──► create_customer()
    └──► create_load(customer)
    └──► create_leg(load)
    └──► create_stops(leg)
    └──► assign_carrier_driver(leg)  <── Fifth step
            └──► carrier_factory.get_carrier_driver_pair()
            └──► ShipmentAssignmentFactory.create(...)
```

---

### `create_complete_load(self) -> LoadCreationResult`

Orchestrates the complete load creation workflow.

#### Returns

| Type | Description |
|------|-------------|
| `LoadCreationResult` | Dictionary containing all created objects |

#### Return Value Structure

```python
{
    'customer': Customer,        # Customer with address
    'load': Load,               # Load with customer association
    'leg': Leg,                 # Leg with load association
    'stops': List[Stop],        # Stops with addresses and actions
    'assignment': ShipmentAssignment  # Carrier/driver assignment
}
```

#### Behavior

The method is wrapped in `@transaction.atomic` to ensure all-or-nothing behavior. If any step fails, all changes are rolled back.

**Execution Sequence**:
1. Create Customer (with address)
2. Create Load (associated with customer)
3. Create Leg (associated with load)
4. Create Stops (associated with leg, using addresses from pool)
5. Create ShipmentAssignment (carrier/driver assigned to leg)

#### Usage Example

```python
from machtms.core.factories.creator_factories import (
    FakeAddressCreator,
    FakeCarrierCreator,
    LoadCreationFactory,
)

# Setup
address_creator = FakeAddressCreator(N=30)
carrier_creator = FakeCarrierCreator(carriers_length=10)

factory = LoadCreationFactory(
    stop_length=2,
    carrier_factory=carrier_creator,
    address_factory=address_creator,
)

# Create complete load
result = factory.create_complete_load()

# Access created objects
print(f"Customer: {result['customer'].customer_name}")
print(f"Load: {result['load'].reference_number}")
print(f"Leg ID: {result['leg'].id}")
print(f"Stops: {len(result['stops'])}")
for stop in result['stops']:
    print(f"  Stop {stop.stop_number}: {stop.action} at {stop.address.city}")
print(f"Carrier: {result['assignment'].carrier.carrier_name}")
print(f"Driver: {result['assignment'].driver.first_name}")
```

---

## Complete Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                LoadCreationFactory Pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    @transaction.atomic                   │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │                                                          │    │
│  │  Step 1: create_customer()                               │    │
│  │      └──► CustomerFactory.create()                       │    │
│  │              └──► Address created (unique)               │    │
│  │              └──► Customer created                       │    │
│  │                                                          │    │
│  │  Step 2: create_load(customer)                           │    │
│  │      └──► LoadFactory.create(customer=customer, ...)     │    │
│  │              └──► Load with PENDING status               │    │
│  │              └──► Random trailer_type                    │    │
│  │                                                          │    │
│  │  Step 3: create_leg(load)                                │    │
│  │      └──► LegFactory.create(load=load)                   │    │
│  │                                                          │    │
│  │  Step 4: create_stops(leg)                               │    │
│  │      └──► address_factory.get_address_tuple()            │    │
│  │      └──► For each address:                              │    │
│  │              └──► Determine action (LL/HL/HUBP/LU/LD)    │    │
│  │              └──► Set time windows                       │    │
│  │              └──► Stop.objects.create(...)               │    │
│  │                                                          │    │
│  │  Step 5: assign_carrier_driver(leg)                      │    │
│  │      └──► carrier_factory.get_carrier_driver_pair()      │    │
│  │      └──► ShipmentAssignmentFactory.create(...)          │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│                     LoadCreationResult                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Dependencies

### Internal Dependencies

| Import | Purpose |
|--------|---------|
| `machtms.backend.customers.models.Customer` | Customer model |
| `machtms.backend.legs.models.Leg` | Leg model |
| `machtms.backend.legs.models.ShipmentAssignment` | Assignment model |
| `machtms.backend.loads.models.Load` | Load model |
| `machtms.backend.loads.models.LoadStatus` | Load status enum |
| `machtms.backend.loads.models.BillingStatus` | Billing status enum |
| `machtms.backend.loads.models.TrailerType` | Trailer type enum |
| `machtms.backend.routes.models.Stop` | Stop model |
| `machtms.core.factories.customer.CustomerFactory` | Customer factory |
| `machtms.core.factories.leg.LegFactory` | Leg factory |
| `machtms.core.factories.leg.ShipmentAssignmentFactory` | Assignment factory |
| `machtms.core.factories.loads.LoadFactory` | Load factory |

### External Dependencies

| Import | Purpose |
|--------|---------|
| `django.db.transaction` | For atomic database operations |
| `django.utils.timezone` | For timezone-aware datetime |
| `datetime.timedelta` | For time calculations |
| `random` | For random selections |
| `typing` | For type hints, Protocol, TypedDict |

---

## Design Notes

1. **Composition Over Inheritance**: Uses composition to coordinate multiple factories rather than extending them.

2. **Protocol-Based Design**: Uses Python Protocols to define interfaces for carrier and address factories, enabling loose coupling and easy testing with mock objects.

3. **Atomic Transactions**: The `create_complete_load()` method uses `@transaction.atomic` to ensure data consistency.

4. **Single Responsibility**: Each method handles one specific step in the load creation process.

5. **Configurable Stop Length**: Supports both 2-stop (simple pickup/delivery) and 3-stop (with intermediate hub) routes.

6. **Realistic Data Generation**: Uses random selections for trailer types, stop actions, and time offsets to generate varied, realistic data.
