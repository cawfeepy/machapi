# Prebuilt Module (`prebuilt.py`)

## File Overview

The `prebuilt.py` module provides convenience functions for batch load creation in the machTMS transportation management system. It offers high-level functions that abstract away the complexity of setting up factories and creating multiple loads, making it ideal for quick test data generation and simulation purposes.

### Purpose

While `LoadCreationFactory` handles creating individual loads, and `FakeAddressCreator`/`FakeCarrierCreator` manage resource pools, the prebuilt module provides simple entry points for common use cases:
- Quick generation of test data with sensible defaults
- Batch creation with configurable parameters
- One-liner data seeding for development and testing

### Role in Application Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Prebuilt Module Layer                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User Code                                                      │
│       │                                                          │
│       ▼                                                          │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  quick_create() or create_batch_loads()                  │  │
│   └──────────────────────────────────────────────────────────┘  │
│       │                                                          │
│       ▼                                                          │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  FakeAddressCreator + FakeCarrierCreator                 │  │
│   └──────────────────────────────────────────────────────────┘  │
│       │                                                          │
│       ▼                                                          │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  LoadCreationFactory.create_complete_load() (N times)    │  │
│   └──────────────────────────────────────────────────────────┘  │
│       │                                                          │
│       ▼                                                          │
│   List[LoadCreationResult]                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Functions

### `_validate_batch_parameters(...) -> None`

**Private Function** - Validates parameters for batch load creation.

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `load_count` | `int` | Number of loads to create |
| `address_pool_size` | `int` | Size of the address pool |
| `carrier_count` | `int` | Number of carriers to create |
| `stops_per_load` | `int` | Number of stops per load |

#### Raises

| Exception | Condition |
|-----------|-----------|
| `ValueError` | If `load_count < 1` |
| `ValueError` | If `address_pool_size < 1` |
| `ValueError` | If `carrier_count < 1` |
| `ValueError` | If `stops_per_load` is not 2 or 3 |
| `ValueError` | If `address_pool_size < load_count * stops_per_load` |

#### Validation Logic

The function ensures that there are enough addresses in the pool for all loads:

```
minimum_addresses_required = load_count * stops_per_load
```

If `address_pool_size` is less than this minimum, an error is raised with a helpful message.

---

### `_import_creator_classes() -> tuple`

**Private Function** - Imports FakeAddressCreator and FakeCarrierCreator classes.

#### Returns

| Type | Description |
|------|-------------|
| `tuple` | Tuple of (FakeAddressCreator, FakeCarrierCreator) classes |

#### Raises

| Exception | Condition |
|-----------|-----------|
| `ImportError` | If the creator classes are not available |

#### Purpose

This function uses lazy importing to avoid circular import issues and provides a clear error message if the required classes are not available.

---

### `create_batch_loads(...) -> List[LoadCreationResult]`

Creates multiple complete loads with all associated objects.

#### Signature

```python
def create_batch_loads(
    load_count: int,
    address_pool_size: int,
    carrier_count: int,
    stops_per_load: int = 2,
) -> List[LoadCreationResult]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `load_count` | `int` | Yes | - | Number of loads to create |
| `address_pool_size` | `int` | Yes | - | Size of the address pool for FakeAddressCreator |
| `carrier_count` | `int` | Yes | - | Number of carriers to create in FakeCarrierCreator |
| `stops_per_load` | `int` | No | `2` | Number of stops per load (2 or 3) |

#### Returns

| Type | Description |
|------|-------------|
| `List[LoadCreationResult]` | List of dictionaries, each containing created objects |

Each `LoadCreationResult` contains:

| Key | Type | Description |
|-----|------|-------------|
| `customer` | `Customer` | Customer instance |
| `load` | `Load` | Load instance |
| `leg` | `Leg` | Leg instance |
| `stops` | `List[Stop]` | List of Stop instances |
| `assignment` | `ShipmentAssignment` | ShipmentAssignment instance |

#### Raises

| Exception | Condition |
|-----------|-----------|
| `ValueError` | If any count parameter is < 1 |
| `ValueError` | If stops_per_load is not 2 or 3 |
| `ValueError` | If address_pool_size is too small |
| `ImportError` | If creator classes are not available |

#### Behavior

1. Validates all input parameters
2. Imports creator classes (lazy import)
3. Creates `FakeAddressCreator` with specified pool size
4. Creates `FakeCarrierCreator` with specified carrier count
5. Within a single atomic transaction:
   - Creates `load_count` number of `LoadCreationFactory` instances
   - Calls `create_complete_load()` for each
   - Collects results into a list
6. Returns the list of results

#### Transaction Handling

The entire batch creation is wrapped in `transaction.atomic()`:

```python
with transaction.atomic():
    for _ in range(load_count):
        factory = LoadCreationFactory(...)
        result = factory.create_complete_load()
        results.append(result)
```

This ensures that either all loads are created successfully, or none are created (rollback on failure).

#### Usage Example

```python
from machtms.core.factories.creator_factories import create_batch_loads

# Create 10 loads with 2 stops each
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
```

#### Advanced Example

```python
from machtms.core.factories.creator_factories import create_batch_loads

# Create 50 loads with 3 stops each (more complex routes)
results = create_batch_loads(
    load_count=50,
    address_pool_size=200,  # Need more addresses for 3-stop routes
    carrier_count=20,
    stops_per_load=3
)

# Analyze created data
total_stops = sum(len(r['stops']) for r in results)
unique_carriers = set(r['assignment'].carrier.id for r in results)

print(f"Created {len(results)} loads")
print(f"Total stops: {total_stops}")
print(f"Unique carriers used: {len(unique_carriers)}")
```

---

### `quick_create(num_loads: int = 10) -> List[LoadCreationResult]`

Convenience function for quickly creating test loads with sensible defaults.

#### Signature

```python
def quick_create(num_loads: int = 10) -> List[LoadCreationResult]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `num_loads` | `int` | No | `10` | Number of loads to create |

#### Returns

| Type | Description |
|------|-------------|
| `List[LoadCreationResult]` | List of created load data dictionaries |

#### Default Calculations

The function calculates sensible defaults based on `num_loads`:

| Parameter | Formula | Purpose |
|-----------|---------|---------|
| `address_pool_size` | `num_loads * 3` | Ensures enough unique addresses |
| `carrier_count` | `max(5, num_loads // 2)` | Reasonable carrier diversity |
| `stops_per_load` | `2` | Standard pickup/delivery |

#### Raises

| Exception | Condition |
|-----------|-----------|
| `ValueError` | If `num_loads < 1` |

#### Side Effects

Prints a summary message after creation:
```
Created {num_loads} loads with {total_stops} stops
```

#### Usage Examples

```python
from machtms.core.factories.creator_factories import quick_create

# Create 10 loads with defaults
results = quick_create()
# Output: Created 10 loads with 20 stops

# Create 50 loads
results = quick_create(50)
# Output: Created 50 loads with 100 stops

# Access created data
for result in results:
    print(f"Load: {result['load'].reference_number}")
    print(f"  Customer: {result['customer'].customer_name}")
    print(f"  Carrier: {result['assignment'].carrier.carrier_name}")
```

#### When to Use `quick_create` vs `create_batch_loads`

| Scenario | Recommended Function |
|----------|---------------------|
| Quick test data generation | `quick_create()` |
| Development database seeding | `quick_create(num_loads=100)` |
| Need specific address pool size | `create_batch_loads()` |
| Need specific carrier count | `create_batch_loads()` |
| Need 3-stop routes | `create_batch_loads(stops_per_load=3)` |
| Performance testing with large datasets | `create_batch_loads()` |

---

## Complete Usage Examples

### Django Management Command

```python
# management/commands/seed_loads.py
from django.core.management.base import BaseCommand
from machtms.core.factories.creator_factories import quick_create

class Command(BaseCommand):
    help = 'Seed database with test loads'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of loads to create'
        )

    def handle(self, *args, **options):
        count = options['count']
        results = quick_create(count)
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {len(results)} loads')
        )
```

### Test Setup

```python
# tests/test_loads.py
from django.test import TestCase
from machtms.core.factories.creator_factories import create_batch_loads

class LoadProcessingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create 5 loads for testing
        cls.test_loads = create_batch_loads(
            load_count=5,
            address_pool_size=15,
            carrier_count=3,
            stops_per_load=2
        )

    def test_load_has_customer(self):
        for result in self.test_loads:
            self.assertIsNotNone(result['load'].customer)
            self.assertEqual(
                result['load'].customer,
                result['customer']
            )

    def test_load_has_correct_stop_count(self):
        for result in self.test_loads:
            self.assertEqual(len(result['stops']), 2)
```

### Interactive Shell / Django Shell

```python
# In Django shell: python manage.py shell
from machtms.core.factories.creator_factories import quick_create

# Quick data generation for exploration
results = quick_create(5)

# Explore the data
load = results[0]['load']
print(f"Reference: {load.reference_number}")
print(f"Status: {load.status}")
print(f"Customer: {load.customer.customer_name}")

# Check stops
for stop in results[0]['stops']:
    print(f"Stop {stop.stop_number}: {stop.action} at {stop.address.city}")
```

---

## Dependencies

### Internal Dependencies

| Import | Purpose |
|--------|---------|
| `machtms.core.factories.creator_factories.fake_address_creator.FakeAddressCreator` | Address pool creation |
| `machtms.core.factories.creator_factories.fake_carrier_creator.FakeCarrierCreator` | Carrier pool creation |
| `machtms.core.factories.creator_factories.load_creation.LoadCreationFactory` | Load creation orchestration |
| `machtms.core.factories.creator_factories.load_creation.LoadCreationResult` | Return type definition |

### External Dependencies

| Import | Purpose |
|--------|---------|
| `django.db.transaction` | For atomic batch creation |
| `typing.List` | Type hints |

---

## Design Notes

1. **Facade Pattern**: These functions act as a facade, providing simple interfaces to complex underlying systems.

2. **Lazy Imports**: Creator classes are imported inside functions to avoid circular import issues and improve module load time.

3. **Sensible Defaults**: `quick_create()` calculates pool sizes automatically based on load count, reducing the cognitive load for common use cases.

4. **Validation First**: Both functions validate inputs before any database operations, failing fast with clear error messages.

5. **Atomic Operations**: Batch creation is wrapped in a transaction to ensure data consistency.

6. **Console Feedback**: `quick_create()` prints a summary, providing immediate feedback for interactive use.
