# LoadViewSet API Documentation

This document describes how to use the Load API endpoints from the client side.

## Base URL

```
/api/loads/
```

## Endpoints Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/loads/` | GET | List all loads |
| `/api/loads/` | POST | Create a new load |
| `/api/loads/{id}/` | GET | Retrieve a specific load |
| `/api/loads/{id}/` | PUT | Update a load (full) |
| `/api/loads/{id}/` | PATCH | Update a load (partial) |
| `/api/loads/{id}/` | DELETE | Delete a load |
| `/api/loads/calendar-day/` | GET | Get loads for a specific day |
| `/api/loads/calendar-week/` | GET | Get loads grouped by week |

---

## Calendar Day Endpoint

**Primary endpoint for calendar views.** Returns loads with pickup stops on a specific date.

### Request

```
GET /api/loads/calendar-day/?date=2024-02-05
```

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `date` | string (YYYY-MM-DD) | No | Today | The date to fetch loads for |

### Response

```json
{
  "date": "2024-02-05",
  "day_name": "monday",
  "total_loads": 5,
  "unassigned_count": 2,
  "loads": [
    {
      "id": 42,
      "reference_number": "REF-000042",
      "bol_number": "BOL-000042",
      "status": "pending",
      "billing_status": "pending_delivery",
      "trailer_type": "LARGE_53",
      "has_unassigned_leg": true,
      "first_pickup_time": "2024-02-05T08:00:00Z",
      "customer": {
        "id": 1,
        "customer_name": "Acme Shipping",
        "phone_number": "555-1234"
      },
      "legs": [
        {
          "id": 101,
          "is_assigned": false,
          "shipment_assignments": [],
          "stops": [
            {
              "id": 201,
              "stop_number": 1,
              "action": "LL",
              "action_display": "LIVE LOAD",
              "start_range": "2024-02-05T08:00:00Z",
              "end_range": "2024-02-05T10:00:00Z",
              "po_numbers": "PO-12345",
              "address": {
                "id": 10,
                "street": "123 Pickup Lane",
                "city": "Chicago",
                "state": "IL",
                "zip_code": "60601"
              }
            },
            {
              "id": 202,
              "stop_number": 2,
              "action": "LU",
              "action_display": "LIVE UNLOAD",
              "start_range": "2024-02-05T14:00:00Z",
              "end_range": "2024-02-05T16:00:00Z",
              "po_numbers": "",
              "address": { ... }
            }
          ]
        }
      ],
      "created_at": "2024-01-28T10:30:00Z",
      "updated_at": "2024-01-28T10:30:00Z"
    }
  ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | The queried date (YYYY-MM-DD) |
| `day_name` | string | Day of week (lowercase: monday, tuesday, etc.) |
| `total_loads` | integer | Total number of loads returned |
| `unassigned_count` | integer | Number of loads with unassigned legs |
| `loads` | array | Array of load objects |

### Load Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Load ID |
| `reference_number` | string | Load reference number |
| `bol_number` | string | Bill of Lading number |
| `status` | string | Load status (pending, assigned, dispatched, etc.) |
| `billing_status` | string | Billing status |
| `trailer_type` | string | Trailer type code |
| `has_unassigned_leg` | boolean | True if any leg lacks a ShipmentAssignment |
| `first_pickup_time` | datetime | Earliest pickup time on this day |
| `customer` | object | Nested customer data |
| `legs` | array | Array of leg objects |

### Leg Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Leg ID |
| `is_assigned` | boolean | True if leg has a ShipmentAssignment |
| `shipment_assignments` | array | Array of assignment objects with carrier/driver |
| `stops` | array | Array of stop objects |

### Sorting Behavior

Loads are sorted in this order:
1. **Unassigned first** - Loads where `has_unassigned_leg: true` appear at the top
2. **Then by pickup time** - Earliest `first_pickup_time` first

### Client Usage Examples

#### JavaScript/TypeScript

```typescript
// Fetch loads for a specific date
async function getLoadsForDay(date: string): Promise<CalendarDayResponse> {
  const response = await fetch(`/api/loads/calendar-day/?date=${date}`, {
    headers: {
      'Authorization': `Token ${authToken}`,
      'Content-Type': 'application/json',
    },
  });
  return response.json();
}

// Example: Get loads for February 5th, 2024
const data = await getLoadsForDay('2024-02-05');
console.log(`${data.total_loads} loads on ${data.day_name}`);
console.log(`${data.unassigned_count} need assignment`);

// Render loads
data.loads.forEach(load => {
  if (load.has_unassigned_leg) {
    renderUnassignedLoad(load);
  } else {
    renderAssignedLoad(load);
  }
});
```

#### React Hook Example

```typescript
function useCalendarDay(date: string) {
  const [data, setData] = useState<CalendarDayResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/loads/calendar-day/?date=${date}`)
      .then(res => res.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, [date]);

  return { data, loading };
}

// Usage in component
function DayView({ selectedDate }: { selectedDate: string }) {
  const { data, loading } = useCalendarDay(selectedDate);

  if (loading) return <Spinner />;

  return (
    <div>
      <h2>{data.day_name} - {data.date}</h2>
      <p>{data.unassigned_count} loads need assignment</p>
      {data.loads.map(load => (
        <LoadCard key={load.id} load={load} />
      ))}
    </div>
  );
}
```

---

## Calendar Week Endpoint

Returns loads grouped by day for a Sunday-Saturday week.

### Request

```
GET /api/loads/calendar-week/?week_start=2024-02-04
```

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `week_start` | string (YYYY-MM-DD) | No | Current week's Sunday | Sunday of the desired week |

### Response

```json
{
  "week_start": "2024-02-04",
  "week_end": "2024-02-10",
  "total_loads": 15,
  "unassigned_count": 4,
  "days": {
    "sunday": [],
    "monday": [
      {
        "id": 42,
        "reference_number": "REF-000042",
        "has_unassigned_leg": true,
        "first_pickup_time": "2024-02-05T08:00:00Z",
        ...
      }
    ],
    "tuesday": [...],
    "wednesday": [...],
    "thursday": [...],
    "friday": [...],
    "saturday": []
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `week_start` | string | Sunday of the week (YYYY-MM-DD) |
| `week_end` | string | Saturday of the week (YYYY-MM-DD) |
| `total_loads` | integer | Total unique loads in the week |
| `unassigned_count` | integer | Loads with unassigned legs |
| `days` | object | Object with day names as keys, load arrays as values |

### Multi-Day Loads

A load with pickup stops on multiple days will appear in each day's array. For example, a load with pickups on Monday and Wednesday will appear in both `days.monday` and `days.wednesday`.

### Client Usage Example

```typescript
// Fetch entire week
async function getWeekLoads(weekStart: string): Promise<CalendarWeekResponse> {
  const response = await fetch(`/api/loads/calendar-week/?week_start=${weekStart}`);
  return response.json();
}

// Navigate weeks
function WeekNavigator({ currentSunday, onWeekChange }) {
  const prevWeek = () => {
    const prev = new Date(currentSunday);
    prev.setDate(prev.getDate() - 7);
    onWeekChange(prev.toISOString().split('T')[0]);
  };

  const nextWeek = () => {
    const next = new Date(currentSunday);
    next.setDate(next.getDate() + 7);
    onWeekChange(next.toISOString().split('T')[0]);
  };

  return (
    <div>
      <button onClick={prevWeek}>Previous Week</button>
      <button onClick={nextWeek}>Next Week</button>
    </div>
  );
}
```

---

## Pickup Actions

The calendar endpoints filter loads based on pickup stop actions. Only these stop actions are considered "pickup" actions:

| Code | Description |
|------|-------------|
| `LL` | Live Load |
| `HL` | Hook Loaded |
| `EMPP` | Empty Pickup |
| `HUBP` | Hub Pickup |

Delivery actions (`LU`, `LD`, `EMPD`, `HUBD`) do not place loads in a day's calendar.

---

## Load Statuses

| Status | Description |
|--------|-------------|
| `pending` | Load created, not yet assigned |
| `assigned` | Carrier/driver assigned |
| `dispatched` | Dispatched to driver |
| `in_transit` | Currently in transit |
| `times_missing` | Awaiting time updates |
| `rescheduled` | Pickup/delivery rescheduled |
| `claim` | Claim filed |
| `at_hub` | At hub location |
| `complete` | Delivered successfully |
| `tonu` | Truck Ordered Not Used |

---

## TypeScript Interfaces

```typescript
interface Address {
  id: number;
  street: string;
  city: string;
  state: string;
  zip_code: string;
  country?: string;
  latitude?: string;
  longitude?: string;
}

interface Customer {
  id: number;
  customer_name: string;
  phone_number?: string;
}

interface Carrier {
  id: number;
  carrier_name: string;
  phone?: string;
  contractor: boolean;
  driver_count?: number;
}

interface Driver {
  id: number;
  full_name: string;
  phone_number?: string;
  carrier: number;
}

interface ShipmentAssignment {
  id: number;
  carrier: Carrier;
  driver: Driver;
}

interface Stop {
  id: number;
  stop_number: number;
  action: 'LL' | 'LU' | 'HL' | 'LD' | 'EMPP' | 'EMPD' | 'HUBP' | 'HUBD';
  action_display: string;
  start_range: string;
  end_range: string | null;
  po_numbers: string;
  address: Address;
}

interface Leg {
  id: number;
  is_assigned: boolean;
  shipment_assignments: ShipmentAssignment[];
  stops: Stop[];
}

interface LoadDaily {
  id: number;
  reference_number: string;
  bol_number: string;
  status: string;
  billing_status: string;
  trailer_type: string;
  has_unassigned_leg: boolean;
  first_pickup_time: string | null;
  customer: Customer;
  legs: Leg[];
  created_at: string;
  updated_at: string;
}

interface CalendarDayResponse {
  date: string;
  day_name: string;
  total_loads: number;
  unassigned_count: number;
  loads: LoadDaily[];
}

interface CalendarWeekResponse {
  week_start: string;
  week_end: string;
  total_loads: number;
  unassigned_count: number;
  days: {
    sunday: LoadDaily[];
    monday: LoadDaily[];
    tuesday: LoadDaily[];
    wednesday: LoadDaily[];
    thursday: LoadDaily[];
    friday: LoadDaily[];
    saturday: LoadDaily[];
  };
}
```

---

## Error Responses

### 401 Unauthorized

```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden

```json
{
  "detail": "You do not have permission to perform this action."
}
```

---

## Best Practices

1. **Use calendar-day for single day views** - More efficient than fetching the entire week
2. **Cache week data** - When displaying a week calendar, fetch once and filter client-side
3. **Handle unassigned loads prominently** - They appear first for a reason
4. **Use TypeScript interfaces** - Provides type safety for API responses
5. **Handle empty days** - Days with no loads return empty arrays, not null
