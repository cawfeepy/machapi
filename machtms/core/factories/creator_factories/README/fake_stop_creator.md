# fake_stop_creator.py

## Overview

The `fake_stop_creator.py` module provides the `FakeStopCreator` class for generating `Stop` instances associated with existing `Leg` objects. This module is designed for testing stop-specific functionality or adding stops to legs without using the full load creation workflow.

### Purpose
- Generate realistic stop data for transportation routes in test scenarios
- Handle proper stop sequencing and action assignment based on position
- Provide batch creation capabilities for multiple legs
- Track all stops created through a single creator instance

### Role in Architecture
This module serves as a specialized factory creator within the machTMS test data generation system. It sits between the low-level `StopFactory` (factory_boy) and higher-level load creation workflows, allowing isolated stop generation when full load creation is unnecessary.

---

## Dependencies

| Import | Source | Purpose |
|--------|--------|---------|
| `random` | Python stdlib | Random selection of stop actions |
| `timedelta` | `datetime` | Time offset calculations for stop time ranges |
| `List`, `Optional`, `TypeAlias` | `typing` | Type annotations |
| `timezone` | `django.utils` | Timezone-aware datetime handling |
| `Leg` | `machtms.backend.legs.models` | The Leg model that stops belong to |
| `Stop` | `machtms.backend.routes.models` | The Stop model being created |
| `StopFactory` | `machtms.core.factories.routes` | Factory for creating Stop instances |

---

## Type Aliases

```python
StopList: TypeAlias = List[Stop]
```

A type alias for `List[Stop]` used throughout the module for clarity.

---

## Class: FakeStopCreator

### Description

Creates and manages fake stops for legs in test scenarios. This class generates `Stop` instances using `StopFactory` for existing `Leg` objects, handling proper stop numbering, action assignment based on position, and realistic time ranges.

### Class Attributes

| Attribute | Type | Value | Description |
|-----------|------|-------|-------------|
| `FIRST_STOP_ACTIONS` | `List[str]` | `["LL", "HL"]` | Valid actions for the first stop (pickup actions) |
| `MIDDLE_STOP_ACTIONS` | `List[str]` | `["HUBP", "HUBD"]` | Valid actions for middle stops (hub actions) |
| `LAST_STOP_ACTIONS` | `List[str]` | `["LU", "LD"]` | Valid actions for the last stop (delivery actions) |

### Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `stops` | `StopList` | List of all Stop instances created by this creator |

### Action Codes Reference

| Code | Full Name | Position |
|------|-----------|----------|
| `LL` | Live Load | First stop |
| `HL` | Hook Loaded | First stop |
| `HUBP` | Hub Pickup | Middle stop |
| `HUBD` | Hub Dropoff | Middle stop |
| `LU` | Live Unload | Last stop |
| `LD` | Drop Loaded | Last stop |

---

## Methods

### `__init__(self) -> None`

Initialize a new `FakeStopCreator` instance.

**Purpose:** Creates an empty list to track all stops created by this instance.

**Parameters:** None

**Returns:** None

**Example:**
```python
creator = FakeStopCreator()
```

---

### `_determine_action(self, stop_index: int, total_stops: int) -> str`

Determine the appropriate action for a stop based on its position within the leg.

**Purpose:** Maps stop position to appropriate action codes (pickup for first, hub for middle, delivery for last).

**Pipeline Position:** Called internally by `create_stops_for_leg` during stop generation.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `stop_index` | `int` | Zero-based index of the stop within the leg |
| `total_stops` | `int` | Total number of stops being created |

**Returns:** `str` - Action code (e.g., `'LL'`, `'LU'`, `'HUBP'`)

**Logic:**
```
stop_index == 0           --> FIRST_STOP_ACTIONS (pickup)
stop_index == total - 1   --> LAST_STOP_ACTIONS (delivery)
otherwise                 --> MIDDLE_STOP_ACTIONS (hub)
```

**Example:**
```python
creator = FakeStopCreator()
action = creator._determine_action(0, 3)   # Returns 'LL' or 'HL'
action = creator._determine_action(1, 3)   # Returns 'HUBP' or 'HUBD'
action = creator._determine_action(2, 3)   # Returns 'LU' or 'LD'
```

---

### `create_stops_for_leg(self, leg: Leg, num_stops: int = 2, base_date: Optional[timezone.datetime] = None) -> StopList`

Create stops for a given leg with proper sequencing and time ranges.

**Purpose:** Generates the specified number of stops with sequential numbering, position-appropriate actions, auto-generated addresses, and time ranges spaced 4 hours apart.

**Pipeline Position:** Main entry point for stop creation. Can be called directly or via `create_batch_stops`.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `leg` | `Leg` | (required) | Leg instance to associate stops with |
| `num_stops` | `int` | `2` | Number of stops to create (must be 2 or 3) |
| `base_date` | `Optional[timezone.datetime]` | `None` | Starting datetime for stop time ranges |

**Returns:** `StopList` - List of created `Stop` instances ordered by `stop_number`

**Raises:** `ValueError` - If `num_stops` is not 2 or 3

**Time Range Calculation:**
- If `base_date` is `None`, defaults to `now + random(1-7) days`
- Each stop is spaced 4 hours apart
- Each stop has a 2-hour window (`start_range` to `end_range`)

```
Stop 1: base_date + 0h  to  base_date + 2h
Stop 2: base_date + 4h  to  base_date + 6h
Stop 3: base_date + 8h  to  base_date + 10h
```

**Example:**
```python
from machtms.backend.legs.models import Leg

creator = FakeStopCreator()
leg = Leg.objects.first()

# Create 2 stops (pickup and delivery)
stops = creator.create_stops_for_leg(leg, num_stops=2)

# Create 3 stops with custom base date
from django.utils import timezone
from datetime import timedelta

base = timezone.now() + timedelta(days=3)
stops = creator.create_stops_for_leg(leg, num_stops=3, base_date=base)
```

---

### `create_batch_stops(self, legs: List[Leg], stops_per_leg: int = 2) -> List[StopList]`

Create stops for multiple legs at once.

**Purpose:** Convenience method for generating stops across multiple legs, useful for bulk test data generation.

**Pipeline Position:** Higher-level batch operation that iterates and calls `create_stops_for_leg` for each leg.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `legs` | `List[Leg]` | (required) | List of Leg instances to create stops for |
| `stops_per_leg` | `int` | `2` | Number of stops per leg (2 or 3) |

**Returns:** `List[StopList]` - List of stop lists, one for each leg

**Example:**
```python
from machtms.backend.legs.models import Leg

creator = FakeStopCreator()
legs = list(Leg.objects.all()[:5])

# Create 2 stops per leg for 5 legs (10 stops total)
all_stops = creator.create_batch_stops(legs, stops_per_leg=2)

for i, leg_stops in enumerate(all_stops):
    print(f"Leg {i+1}: {len(leg_stops)} stops created")
```

---

### `get_all_stops(self) -> StopList`

Return all stops created by this `FakeStopCreator` instance.

**Purpose:** Retrieve the complete list of stops created across all calls to `create_stops_for_leg` or `create_batch_stops`.

**Pipeline Position:** Accessor method, called after stop creation to retrieve results.

**Parameters:** None

**Returns:** `StopList` - List of all `Stop` instances created by this creator

**Example:**
```python
creator = FakeStopCreator()
creator.create_stops_for_leg(leg1)
creator.create_stops_for_leg(leg2)
creator.create_stops_for_leg(leg3)

# Get all stops from all three legs
all_stops = creator.get_all_stops()
print(f"Total stops created: {len(all_stops)}")
```

---

### `get_stop_count(self) -> int`

Return the total number of stops created by this instance.

**Purpose:** Quick count accessor without needing to retrieve the full list.

**Pipeline Position:** Accessor method, called after stop creation for statistics.

**Parameters:** None

**Returns:** `int` - Integer count of all stops created

**Example:**
```python
creator = FakeStopCreator()
creator.create_batch_stops(legs, stops_per_leg=3)
print(f"Created {creator.get_stop_count()} total stops")
```

---

## Workflow Diagrams

### Single Leg Stop Creation

```
create_stops_for_leg(leg, num_stops=3)
    |
    |---> Validate num_stops (must be 2 or 3)
    |
    |---> Calculate base_date if None
    |         └──> timezone.now() + random(1-7) days
    |
    └──> For each stop_index in range(num_stops):
            |
            ├──> _determine_action(stop_index, num_stops)
            |       └──> Returns action code based on position
            |
            ├──> Calculate time ranges
            |       ├──> start_range = base_date + (4 * stop_index) hours
            |       └──> end_range = start_range + 2 hours
            |
            └──> StopFactory.create(...)
                    ├──> leg=leg
                    ├──> stop_number=stop_index + 1
                    ├──> action=action
                    ├──> start_range=start_range
                    ├──> end_range=end_range
                    └──> address=<auto-generated via AddressFactory SubFactory>
```

### Batch Stop Creation

```
create_batch_stops(legs, stops_per_leg=2)
    |
    └──> For each leg in legs:
            |
            └──> create_stops_for_leg(leg, num_stops=stops_per_leg)
                    └──> [Returns StopList for this leg]
```

### Stop Action Assignment Logic

```
_determine_action(stop_index, total_stops)
    |
    ├──> stop_index == 0 (first stop)
    |       └──> random.choice(["LL", "HL"])  <-- Pickup actions
    |
    ├──> stop_index == total_stops - 1 (last stop)
    |       └──> random.choice(["LU", "LD"])  <-- Delivery actions
    |
    └──> Otherwise (middle stop)
            └──> random.choice(["HUBP", "HUBD"])  <-- Hub actions
```

---

## Integration with StopFactory

The `FakeStopCreator` uses `StopFactory` under the hood. Here is how the factory creates stops:

```python
# StopFactory definition (from machtms.core.factories.routes)
class StopFactory(DjangoModelFactory):
    class Meta:
        model = Stop

    leg = factory.SubFactory('machtms.core.factories.leg.LegFactory')
    stop_number = factory.Sequence(lambda n: n + 1)
    address = factory.SubFactory('machtms.core.factories.addresses.AddressFactory')
    start_range = factory.Faker('date_time_this_month', tzinfo=None)
    end_range = factory.Faker('date_time_this_month', tzinfo=None)
    action = factory.Faker('random_element', elements=[...])
    po_numbers = factory.Faker('bothify', text='PO-####-???')
    driver_notes = factory.Faker('sentence', nb_words=10)
```

When `FakeStopCreator` calls `StopFactory.create()`, it overrides:
- `leg` - Uses the provided leg instead of creating a new one
- `stop_number` - Uses sequential numbering starting from 1
- `action` - Uses position-based action instead of random
- `start_range` and `end_range` - Uses calculated time ranges

The factory auto-generates:
- `address` - Via `AddressFactory` SubFactory
- `po_numbers` - Via Faker
- `driver_notes` - Via Faker

---

## Usage Examples

### Basic Usage - Create Stops for a Single Leg

```python
from machtms.backend.legs.models import Leg
from machtms.core.factories.creator_factories.fake_stop_creator import FakeStopCreator

# Get an existing leg
leg = Leg.objects.first()

# Create stops
creator = FakeStopCreator()
stops = creator.create_stops_for_leg(leg, num_stops=2)

# Access created stops
for stop in stops:
    print(f"Stop {stop.stop_number}: {stop.action} at {stop.address}")
```

### Create Stops with Custom Base Date

```python
from datetime import timedelta
from django.utils import timezone
from machtms.core.factories.creator_factories.fake_stop_creator import FakeStopCreator

creator = FakeStopCreator()
leg = Leg.objects.first()

# Schedule stops starting 5 days from now
base_date = timezone.now() + timedelta(days=5)
stops = creator.create_stops_for_leg(leg, num_stops=3, base_date=base_date)

# Verify time ranges
for stop in stops:
    print(f"Stop {stop.stop_number}: {stop.start_range} - {stop.end_range}")
```

### Batch Creation for Multiple Legs

```python
from machtms.backend.legs.models import Leg
from machtms.core.factories.creator_factories.fake_stop_creator import FakeStopCreator

# Get multiple legs
legs = list(Leg.objects.all()[:10])

# Create stops for all legs
creator = FakeStopCreator()
all_stops = creator.create_batch_stops(legs, stops_per_leg=2)

# Summary
print(f"Created stops for {len(legs)} legs")
print(f"Total stops: {creator.get_stop_count()}")

# Access all stops created
for stop in creator.get_all_stops():
    print(f"Leg {stop.leg_id}, Stop {stop.stop_number}: {stop.action}")
```

### Testing Example - Using in a Django Test Case

```python
from django.test import TestCase
from machtms.backend.legs.models import Leg
from machtms.core.factories.leg import LegFactory
from machtms.core.factories.creator_factories.fake_stop_creator import FakeStopCreator


class StopCreationTestCase(TestCase):
    def setUp(self):
        self.creator = FakeStopCreator()
        self.leg = LegFactory.create()

    def test_creates_correct_number_of_stops(self):
        stops = self.creator.create_stops_for_leg(self.leg, num_stops=3)

        self.assertEqual(len(stops), 3)
        self.assertEqual(self.creator.get_stop_count(), 3)

    def test_first_stop_has_pickup_action(self):
        stops = self.creator.create_stops_for_leg(self.leg, num_stops=2)

        self.assertIn(stops[0].action, ['LL', 'HL'])

    def test_last_stop_has_delivery_action(self):
        stops = self.creator.create_stops_for_leg(self.leg, num_stops=2)

        self.assertIn(stops[-1].action, ['LU', 'LD'])

    def test_middle_stop_has_hub_action(self):
        stops = self.creator.create_stops_for_leg(self.leg, num_stops=3)

        self.assertIn(stops[1].action, ['HUBP', 'HUBD'])

    def test_stops_have_sequential_numbering(self):
        stops = self.creator.create_stops_for_leg(self.leg, num_stops=3)

        self.assertEqual([s.stop_number for s in stops], [1, 2, 3])

    def test_invalid_num_stops_raises_error(self):
        with self.assertRaises(ValueError):
            self.creator.create_stops_for_leg(self.leg, num_stops=4)
```

---

## Error Handling

### ValueError for Invalid num_stops

The `create_stops_for_leg` method raises a `ValueError` if `num_stops` is not 2 or 3:

```python
creator = FakeStopCreator()

# This will raise ValueError
try:
    creator.create_stops_for_leg(leg, num_stops=4)
except ValueError as e:
    print(e)  # "num_stops must be 2 or 3, got 4"
```

> **Note:** The restriction to 2 or 3 stops enforces realistic transportation routes where legs typically have a pickup, optional hub, and delivery.

---

## Related Modules

| Module | Description |
|--------|-------------|
| `machtms.core.factories.routes` | Contains `StopFactory` used by this creator |
| `machtms.core.factories.addresses` | Contains `AddressFactory` used as SubFactory in `StopFactory` |
| `machtms.core.factories.leg` | Contains `LegFactory` for creating legs |
| `machtms.backend.routes.models` | Contains the `Stop` model |
| `machtms.backend.legs.models` | Contains the `Leg` model |
