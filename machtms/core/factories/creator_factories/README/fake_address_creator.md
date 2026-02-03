# FakeAddressCreator Module (`fake_address_creator.py`)

## File Overview

The `fake_address_creator.py` module provides the `FakeAddressCreator` class, which generates and organizes fake addresses for load simulation purposes. It creates `Address` instances using the base `AddressFactory` and organizes them into tuples suitable for route simulation in the machTMS transportation management system.

### Purpose

This class solves the problem of generating realistic route data for testing and simulation. In a transportation management system, loads travel between multiple addresses (shipper, stops, receiver). This class creates pools of addresses and organizes them into route tuples that can be consumed by `LoadCreationFactory`.

### Role in Application Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Load Creation Pipeline                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  FakeAddressCreator ──┐                                     │
│  (Address Pool)       │                                     │
│                       ├──► LoadCreationFactory ──► Load     │
│  FakeCarrierCreator ──┘                                     │
│  (Carrier Pool)                                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Type Aliases

The module defines several type aliases for improved code clarity:

| Type Alias | Definition | Description |
|------------|------------|-------------|
| `AddressTuple` | `Tuple[Address, ...]` | Variable-length tuple of Address instances |
| `TwoStopRoute` | `Tuple[Address, Address]` | Exactly 2 addresses (Shipper, Receiver) |
| `ThreeStopRoute` | `Tuple[Address, Address, Address]` | Exactly 3 addresses (Shipper, Stop, Receiver) |
| `AddressList` | `List[Address]` | List of Address instances |

---

## Class: FakeAddressCreator

### Description

Creates and organizes fake addresses for load simulation purposes. Generates N addresses using `AddressFactory` and organizes them into 2-tuples (Shipper, Receiver) and 3-tuples (Shipper, Stop, Receiver) for use in load creation.

### Business Rule Constraint

> **Important**: The address with PK=1 (the first address created, at index 0) can appear as a shipper (first position in tuple) but CANNOT appear as a receiver (last position in any tuple). This enforces the business rule that certain locations are pickup-only.

### Class Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `fakeAddresses` | `List[AddressTuple]` | List of address tuples, each containing 2 or 3 Address instances |

---

## Methods

### `__init__(self, N: int) -> None`

Initializes the FakeAddressCreator and generates N addresses organized into tuples.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `N` | `int` | Yes | Total number of addresses to create. Must be >= 3 |

#### Raises

| Exception | Condition |
|-----------|-----------|
| `ValueError` | If N is less than 3 |

#### Behavior

1. Validates that N >= 3
2. Creates N addresses using `AddressFactory.create()`
3. Designates the first address (index 0) as "shipper-only"
4. Creates a receiver pool excluding the first address
5. Generates address tuples via `_generate_address_tuples()`

#### Usage Example

```python
from machtms.core.factories.creator_factories import FakeAddressCreator

# Create 10 addresses organized into route tuples
address_creator = FakeAddressCreator(N=10)

print(f"Generated {len(address_creator.fakeAddresses)} route tuples")
```

---

### `_generate_address_tuples(self, all_addresses, shipper_only_address, receiver_pool) -> None`

**Private Method** - Generates address tuples ensuring constraints are met.

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `all_addresses` | `AddressList` | All created addresses |
| `shipper_only_address` | `Address` | The address that cannot be a receiver (PK=1) |
| `receiver_pool` | `AddressList` | Addresses that can serve as receivers |

#### Behavior

- Creates approximately N/2 tuples (minimum 2)
- Alternates between 2-tuples and 3-tuples for variety
- Ensures `shipper_only_address` never appears at the last index
- Ensures uniqueness within each tuple

---

### `_create_two_tuple(self, all_addresses, shipper_only_address, receiver_pool) -> TwoStopRoute`

**Private Method** - Creates a 2-tuple (Shipper, Receiver) ensuring constraints are met.

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `all_addresses` | `AddressList` | All created addresses |
| `shipper_only_address` | `Address` | The address that cannot be a receiver |
| `receiver_pool` | `AddressList` | Addresses that can serve as receivers |

#### Returns

| Type | Description |
|------|-------------|
| `TwoStopRoute` | Tuple of (shipper_address, receiver_address) with unique addresses |

#### Behavior

1. Picks a random shipper from all addresses
2. Picks a receiver from receiver_pool, different from shipper
3. Falls back to any receiver_pool address if no different address available

---

### `_create_three_tuple(self, all_addresses, shipper_only_address, receiver_pool) -> ThreeStopRoute`

**Private Method** - Creates a 3-tuple (Shipper, Stop, Receiver) ensuring constraints are met.

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `all_addresses` | `AddressList` | All created addresses |
| `shipper_only_address` | `Address` | The address that cannot be a receiver |
| `receiver_pool` | `AddressList` | Addresses that can serve as receivers |

#### Returns

| Type | Description |
|------|-------------|
| `ThreeStopRoute` | Tuple of (shipper_address, stop_address, receiver_address) with unique addresses |

#### Behavior

1. Picks a random shipper from all addresses
2. Picks a stop different from shipper
3. Picks a receiver from receiver_pool, different from shipper and stop
4. Implements fallback logic if unique selection is not possible

---

### `filterFakeAddresses(self, stop_length: int) -> List[AddressTuple]`

Filters and returns address tuples matching the specified stop_length.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `stop_length` | `int` | Yes | The desired tuple length (typically 2 or 3) |

#### Returns

| Type | Description |
|------|-------------|
| `List[AddressTuple]` | List of address tuples where `len(tuple) == stop_length` |

#### Behavior

- Returns tuples with (Shipper, Receiver) when `stop_length=2`
- Returns tuples with (Shipper, Stop, Receiver) when `stop_length=3`
- Returns empty list if `stop_length` is not 2 or 3

#### Usage Example

```python
address_creator = FakeAddressCreator(N=20)

# Get only 2-stop routes
two_stop_routes = address_creator.filterFakeAddresses(2)
print(f"Found {len(two_stop_routes)} two-stop routes")

# Get only 3-stop routes
three_stop_routes = address_creator.filterFakeAddresses(3)
print(f"Found {len(three_stop_routes)} three-stop routes")
```

---

### `get_address_tuple(self) -> AddressTuple`

Returns a random address tuple from the fakeAddresses list.

#### Returns

| Type | Description |
|------|-------------|
| `AddressTuple` | A random tuple containing 2 or 3 Address instances |

#### Raises

| Exception | Condition |
|-----------|-----------|
| `IndexError` | If fakeAddresses is empty (should not happen with N >= 3) |

#### Pipeline Position

This method implements the `AddressFactoryProtocol` interface expected by `LoadCreationFactory`. It is called during the stop creation phase of the load creation pipeline.

```
LoadCreationFactory.create_stops()
    └──► address_factory.get_address_tuple()  <── This method
            └──► Returns random route for stop creation
```

#### Usage Example

```python
address_creator = FakeAddressCreator(N=15)

# Get a random route tuple
route = address_creator.get_address_tuple()
print(f"Route has {len(route)} stops")

for i, address in enumerate(route):
    print(f"  Stop {i+1}: {address.city}, {address.state}")
```

---

## Complete Usage Example

```python
from machtms.core.factories.creator_factories import (
    FakeAddressCreator,
    FakeCarrierCreator,
    LoadCreationFactory,
)

# Step 1: Create address pool
address_creator = FakeAddressCreator(N=30)
print(f"Created {len(address_creator.fakeAddresses)} route tuples")

# Step 2: Inspect generated routes
for i, route in enumerate(address_creator.fakeAddresses[:5]):
    stops = " -> ".join([f"{addr.city}, {addr.state}" for addr in route])
    print(f"Route {i+1}: {stops}")

# Step 3: Filter by stop count
two_stops = address_creator.filterFakeAddresses(2)
three_stops = address_creator.filterFakeAddresses(3)
print(f"2-stop routes: {len(two_stops)}, 3-stop routes: {len(three_stops)}")

# Step 4: Use with LoadCreationFactory
carrier_creator = FakeCarrierCreator(carriers_length=5)
factory = LoadCreationFactory(
    stop_length=2,
    carrier_factory=carrier_creator,
    address_factory=address_creator,
)
result = factory.create_complete_load()
```

---

## Dependencies

### Internal Dependencies

| Import | Purpose |
|--------|---------|
| `machtms.backend.addresses.models.Address` | The Address model being created |
| `machtms.core.factories.addresses.AddressFactory` | Base factory for creating Address instances |

### External Dependencies

| Import | Purpose |
|--------|---------|
| `random` | For random selection of addresses |
| `typing.List, Tuple, TypeAlias` | Type hint definitions |

---

## Design Notes

1. **Separation of Concerns**: This class only handles address generation and organization. It does not create loads, carriers, or other entities.

2. **Protocol Compliance**: The `get_address_tuple()` method makes this class compatible with `AddressFactoryProtocol` used by `LoadCreationFactory`.

3. **Randomization**: Routes are randomized to simulate realistic variety in load patterns.

4. **Business Logic Encapsulation**: The "shipper-only" constraint for the first address encapsulates a real business rule about certain locations being pickup-only.
