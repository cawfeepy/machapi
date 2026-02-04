from drf_spectacular.utils import OpenApiExample


LOAD_EXAMPLES = [
    OpenApiExample(
        'Create Load Request',
        summary='Create a new load with legs and stops',
        description='Request body for creating a load with nested legs and stops. '
                    'Each leg contains stops that are validated for proper action transitions.',
        value={
            'reference_number': 'LOAD-2024-001',
            'bol_number': 'BOL-12345',
            'customer': 1,
            'status': 'pending',
            'billing_status': 'pending_delivery',
            'trailer_type': 'LARGE_53',
            'legs': [
                {
                    'stops': [
                        {
                            'stop_number': 1,
                            'address': 1,
                            'start_range': '2024-01-15T08:00:00Z',
                            'end_range': '2024-01-15T12:00:00Z',
                            'action': 'LL',
                            'po_numbers': 'PO-12345',
                            'driver_notes': 'Dock 5',
                        },
                        {
                            'stop_number': 2,
                            'address': 2,
                            'start_range': '2024-01-16T08:00:00Z',
                            'end_range': '2024-01-16T12:00:00Z',
                            'action': 'LU',
                            'po_numbers': 'PO-12346',
                            'driver_notes': 'Rear entrance',
                        },
                    ]
                }
            ]
        },
        request_only=True,
    ),
    OpenApiExample(
        'Update Load Request',
        summary='Update existing load with leg and stop IDs',
        description='Include IDs for existing nested objects to update them.',
        value={
            'reference_number': 'LOAD-2024-001-UPDATED',
            'bol_number': 'BOL-12345-REV',
            'status': 'dispatched',
            'legs': [
                {
                    'id': 1,
                    'stops': [
                        {
                            'id': 1,
                            'stop_number': 1,
                            'address': 1,
                            'action': 'LL',
                        },
                        {
                            'id': 2,
                            'stop_number': 2,
                            'address': 2,
                            'action': 'LU',
                        },
                    ]
                }
            ]
        },
        request_only=True,
    ),
    OpenApiExample(
        'Upsert Load Request',
        summary='Update load with mix of existing and new nested objects',
        description='Mix of existing legs/stops (with ID) and new ones (without ID). '
                    'Objects with IDs are updated, objects without IDs are created. '
                    'Existing objects not included in the payload will be deleted.',
        value={
            'reference_number': 'LOAD-2024-001',
            'status': 'in_transit',
            'legs': [
                {
                    'id': 1,
                    'stops': [
                        {
                            'id': 1,
                            'stop_number': 1,
                            'address': 1,
                            'action': 'LL',
                        },
                        {
                            'id': 2,
                            'stop_number': 2,
                            'address': 2,
                            'action': 'LU',
                        },
                    ]
                },
                {
                    'stops': [
                        {
                            'stop_number': 1,
                            'address': 3,
                            'start_range': '2024-01-17T08:00:00Z',
                            'action': 'LL',
                            'driver_notes': 'New leg - second pickup',
                        },
                        {
                            'stop_number': 2,
                            'address': 4,
                            'start_range': '2024-01-18T08:00:00Z',
                            'action': 'LU',
                        },
                    ]
                }
            ]
        },
        request_only=True,
    ),
    OpenApiExample(
        'Load Response',
        summary='Full load response with all nested data',
        description='Response includes all fields with nested legs and stops.',
        value={
            'id': 1,
            'reference_number': 'LOAD-2024-001',
            'bol_number': 'BOL-12345',
            'customer': 1,
            'status': 'pending',
            'billing_status': 'pending_delivery',
            'trailer_type': 'LARGE_53',
            'legs': [
                {
                    'leg_id': 1,
                    'load_id': 1,
                    'stops': [
                        {
                            'id': 1,
                            'leg': 1,
                            'stop_number': 1,
                            'address': 1,
                            'start_range': '2024-01-15T08:00:00Z',
                            'end_range': '2024-01-15T12:00:00Z',
                            'timestamp': '2024-01-10T10:30:00Z',
                            'action': 'LL',
                            'po_numbers': 'PO-12345',
                            'driver_notes': 'Dock 5',
                        },
                        {
                            'id': 2,
                            'leg': 1,
                            'stop_number': 2,
                            'address': 2,
                            'start_range': '2024-01-16T08:00:00Z',
                            'end_range': '2024-01-16T12:00:00Z',
                            'timestamp': '2024-01-10T10:30:00Z',
                            'action': 'LU',
                            'po_numbers': 'PO-12346',
                            'driver_notes': 'Rear entrance',
                        },
                    ],
                }
            ],
            'created_at': '2024-01-10T10:30:00Z',
            'updated_at': '2024-01-10T10:30:00Z',
        },
        response_only=True,
    ),
]

LOAD_LIST_EXAMPLES = [
    OpenApiExample(
        'Load List Response',
        summary='Lightweight load object for list views',
        value={
            'id': 1,
            'invoice_id': 'INV-2024-001',
            'reference_number': 'LOAD-2024-001',
            'customer': 1,
            'income': '1500.00',
            'status': 'pending',
            'billing_status': 'pending_delivery',
            'created_at': '2024-01-10T10:30:00Z',
        },
        response_only=True,
    ),
]


# ============================================================================
# CALENDAR DAY ENDPOINT EXAMPLES
# ============================================================================

CALENDAR_DAY_EXAMPLES = [
    OpenApiExample(
        'Calendar Day Response',
        summary='Loads for a specific day',
        description='Returns loads with pickup stops on the specified date. '
                    'Loads are sorted with unassigned legs first, then by pickup time.',
        value={
            'date': '2024-02-05',
            'day_name': 'monday',
            'total_loads': 3,
            'unassigned_count': 1,
            'loads': [
                {
                    'id': 42,
                    'reference_number': 'REF-000042',
                    'bol_number': 'BOL-000042',
                    'status': 'pending',
                    'billing_status': 'pending_delivery',
                    'trailer_type': 'LARGE_53',
                    'has_unassigned_leg': True,
                    'first_pickup_time': '2024-02-05T08:00:00Z',
                    'customer': {
                        'id': 1,
                        'customer_name': 'Acme Shipping',
                        'phone_number': '555-1234',
                    },
                    'legs': [
                        {
                            'id': 101,
                            'is_assigned': False,
                            'shipment_assignment': [],
                            'stops': [
                                {
                                    'id': 201,
                                    'stop_number': 1,
                                    'action': 'LL',
                                    'action_display': 'LIVE LOAD',
                                    'start_range': '2024-02-05T08:00:00Z',
                                    'end_range': '2024-02-05T10:00:00Z',
                                    'po_numbers': 'PO-12345',
                                    'address': {
                                        'id': 10,
                                        'street': '123 Pickup Lane',
                                        'city': 'Chicago',
                                        'state': 'IL',
                                        'zip_code': '60601',
                                        'country': 'US',
                                    },
                                },
                                {
                                    'id': 202,
                                    'stop_number': 2,
                                    'action': 'LU',
                                    'action_display': 'LIVE UNLOAD',
                                    'start_range': '2024-02-05T14:00:00Z',
                                    'end_range': '2024-02-05T16:00:00Z',
                                    'po_numbers': '',
                                    'address': {
                                        'id': 11,
                                        'street': '456 Delivery Blvd',
                                        'city': 'Detroit',
                                        'state': 'MI',
                                        'zip_code': '48201',
                                        'country': 'US',
                                    },
                                },
                            ],
                        },
                    ],
                    'created_at': '2024-01-28T10:30:00Z',
                    'updated_at': '2024-01-28T10:30:00Z',
                },
                {
                    'id': 43,
                    'reference_number': 'REF-000043',
                    'bol_number': 'BOL-000043',
                    'status': 'assigned',
                    'billing_status': 'pending_delivery',
                    'trailer_type': 'MEDIUM_45',
                    'has_unassigned_leg': False,
                    'first_pickup_time': '2024-02-05T10:00:00Z',
                    'customer': {
                        'id': 2,
                        'customer_name': 'Global Freight Co',
                        'phone_number': '555-5678',
                    },
                    'legs': [
                        {
                            'id': 102,
                            'is_assigned': True,
                            'shipment_assignment': [
                                {
                                    'id': 50,
                                    'carrier': {
                                        'id': 5,
                                        'carrier_name': 'Fast Freight LLC',
                                        'phone': '555-9999',
                                        'contractor': False,
                                        'driver_count': 3,
                                    },
                                    'driver': {
                                        'id': 12,
                                        'full_name': 'John Smith',
                                        'phone_number': '555-8888',
                                        'carrier': 5,
                                    },
                                },
                            ],
                            'stops': [
                                {
                                    'id': 203,
                                    'stop_number': 1,
                                    'action': 'LL',
                                    'action_display': 'LIVE LOAD',
                                    'start_range': '2024-02-05T10:00:00Z',
                                    'end_range': '2024-02-05T12:00:00Z',
                                    'po_numbers': 'PO-67890',
                                    'address': {
                                        'id': 12,
                                        'street': '789 Warehouse Ave',
                                        'city': 'Chicago',
                                        'state': 'IL',
                                        'zip_code': '60602',
                                        'country': 'US',
                                    },
                                },
                            ],
                        },
                    ],
                    'created_at': '2024-01-29T09:00:00Z',
                    'updated_at': '2024-01-30T14:00:00Z',
                },
            ],
        },
        response_only=True,
    ),
    OpenApiExample(
        'Calendar Day Empty Response',
        summary='Empty day with no loads',
        description='Response when no loads have pickup stops on the specified date.',
        value={
            'date': '2024-02-10',
            'day_name': 'saturday',
            'total_loads': 0,
            'unassigned_count': 0,
            'loads': [],
        },
        response_only=True,
    ),
]


# ============================================================================
# CALENDAR WEEK ENDPOINT EXAMPLES
# ============================================================================

CALENDAR_WEEK_EXAMPLES = [
    OpenApiExample(
        'Calendar Week Response',
        summary='Loads grouped by day for a week',
        description='Returns loads organized by day of the week (Sunday-Saturday). '
                    'Loads with pickups on multiple days appear in each relevant day.',
        value={
            'week_start': '2024-02-04',
            'week_end': '2024-02-10',
            'total_loads': 5,
            'unassigned_count': 2,
            'days': {
                'sunday': [],
                'monday': [
                    {
                        'id': 42,
                        'reference_number': 'REF-000042',
                        'has_unassigned_leg': True,
                        'first_pickup_time': '2024-02-05T08:00:00Z',
                        'status': 'pending',
                        'customer': {'id': 1, 'customer_name': 'Acme Shipping'},
                        'legs': [],
                    },
                    {
                        'id': 43,
                        'reference_number': 'REF-000043',
                        'has_unassigned_leg': False,
                        'first_pickup_time': '2024-02-05T10:00:00Z',
                        'status': 'assigned',
                        'customer': {'id': 2, 'customer_name': 'Global Freight'},
                        'legs': [],
                    },
                ],
                'tuesday': [
                    {
                        'id': 44,
                        'reference_number': 'REF-000044',
                        'has_unassigned_leg': True,
                        'first_pickup_time': '2024-02-06T09:00:00Z',
                        'status': 'pending',
                        'customer': {'id': 3, 'customer_name': 'Swift Logistics'},
                        'legs': [],
                    },
                ],
                'wednesday': [],
                'thursday': [
                    {
                        'id': 45,
                        'reference_number': 'REF-000045',
                        'has_unassigned_leg': False,
                        'first_pickup_time': '2024-02-08T07:00:00Z',
                        'status': 'dispatched',
                        'customer': {'id': 1, 'customer_name': 'Acme Shipping'},
                        'legs': [],
                    },
                ],
                'friday': [
                    {
                        'id': 46,
                        'reference_number': 'REF-000046',
                        'has_unassigned_leg': False,
                        'first_pickup_time': '2024-02-09T11:00:00Z',
                        'status': 'assigned',
                        'customer': {'id': 4, 'customer_name': 'Prime Transport'},
                        'legs': [],
                    },
                ],
                'saturday': [],
            },
        },
        response_only=True,
    ),
    OpenApiExample(
        'Calendar Week Empty Response',
        summary='Empty week with no loads',
        description='Response when no loads have pickup stops during the specified week.',
        value={
            'week_start': '2024-12-22',
            'week_end': '2024-12-28',
            'total_loads': 0,
            'unassigned_count': 0,
            'days': {
                'sunday': [],
                'monday': [],
                'tuesday': [],
                'wednesday': [],
                'thursday': [],
                'friday': [],
                'saturday': [],
            },
        },
        response_only=True,
    ),
]
