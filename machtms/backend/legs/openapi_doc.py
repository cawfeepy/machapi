from drf_spectacular.utils import OpenApiExample


SHIPMENT_ASSIGNMENT_MODIFY_EXAMPLES = [
    OpenApiExample(
        'Swap Drivers',
        summary='Swap drivers between two legs',
        description='Delete two existing assignments and create two new ones with swapped drivers. '
                    'Swap operations require exactly 2 items in both to_delete and to_add.',
        value={
            'to_delete': [101, 102],
            'to_add': [
                {'carrier': 1, 'driver': 10, 'leg': 201},
                {'carrier': 1, 'driver': 11, 'leg': 202},
            ]
        },
        request_only=True,
    ),
    OpenApiExample(
        'Unassign Only',
        summary='Remove driver assignments without reassigning',
        description='Delete one or more assignments without creating new ones.',
        value={
            'to_delete': [101, 102],
            'to_add': []
        },
        request_only=True,
    ),
    OpenApiExample(
        'Assign Only',
        summary='Create new driver assignments',
        description='Create new assignments without deleting existing ones.',
        value={
            'to_delete': [],
            'to_add': [
                {'carrier': 1, 'driver': 10, 'leg': 201},
            ]
        },
        request_only=True,
    ),
    OpenApiExample(
        'Modify Response',
        summary='Response after modify operation',
        description='Returns counts and details of deleted and created assignments.',
        value={
            'deleted_count': 2,
            'deleted_ids': [101, 102],
            'created_count': 2,
            'created': [
                {
                    'id': 201,
                    'carrier': {'id': 1, 'carrier_name': 'ABC Trucking'},
                    'driver': {'id': 10, 'full_name': 'John Smith'},
                },
                {
                    'id': 202,
                    'carrier': {'id': 1, 'carrier_name': 'ABC Trucking'},
                    'driver': {'id': 11, 'full_name': 'Jane Doe'},
                },
            ]
        },
        response_only=True,
    ),
]


LEG_EXAMPLES = [
    OpenApiExample(
        'Create Leg Request',
        summary='Create a new leg with stops',
        description='Leg with nested stops for a load. Stops are validated for proper action transitions.',
        value={
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
        },
        request_only=True,
    ),
    OpenApiExample(
        'Create Leg with Shipment Assignments',
        summary='Create a leg with stops and shipment assignments',
        description='Leg with nested stops and shipment assignments. '
                    'Shipment assignments assign a carrier and driver to the leg.',
        value={
            'stops': [
                {
                    'stop_number': 1,
                    'address': 1,
                    'start_range': '2024-01-15T08:00:00Z',
                    'end_range': '2024-01-15T12:00:00Z',
                    'action': 'LL',
                },
                {
                    'stop_number': 2,
                    'address': 2,
                    'start_range': '2024-01-16T08:00:00Z',
                    'end_range': '2024-01-16T12:00:00Z',
                    'action': 'LU',
                },
            ],
            'shipment_assignments': [
                {'carrier': 1, 'driver': 5},
            ]
        },
        request_only=True,
    ),
    OpenApiExample(
        'Update Leg Request',
        summary='Update existing leg with stop IDs',
        description='Include stop IDs to update existing stops.',
        value={
            'id': 1,
            'stops': [
                {
                    'id': 1,
                    'stop_number': 1,
                    'address': 1,
                    'start_range': '2024-01-15T09:00:00Z',
                    'action': 'LL',
                },
                {
                    'id': 2,
                    'stop_number': 2,
                    'address': 3,
                    'action': 'LU',
                },
            ]
        },
        request_only=True,
    ),
    OpenApiExample(
        'Upsert Leg Request',
        summary='Update existing stops and add new stop',
        description='Mix of existing stops (with ID) and new stops (without ID). '
                    'Stops with IDs are updated, stops without IDs are created. '
                    'Existing stops not included in the payload will be deleted.',
        value={
            'id': 1,
            'stops': [
                {
                    'id': 1,
                    'stop_number': 1,
                    'address': 1,
                    'start_range': '2024-01-15T09:00:00Z',
                    'action': 'LL',
                },
                {
                    'id': 2,
                    'stop_number': 2,
                    'address': 2,
                    'action': 'LU',
                },
                {
                    'stop_number': 3,
                    'address': 4,
                    'start_range': '2024-01-17T08:00:00Z',
                    'end_range': '2024-01-17T12:00:00Z',
                    'action': 'EMPD',
                    'driver_notes': 'New stop - drop empty trailer',
                },
            ]
        },
        request_only=True,
    ),
    OpenApiExample(
        'Update Leg with Shipment Assignments',
        summary='Update leg shipment assignments using upsert',
        description='Items with IDs are updated, items without IDs are created. '
                    'Existing assignments not included in payload will be deleted. '
                    'Send empty array to delete all assignments.',
        value={
            'id': 1,
            'shipment_assignments': [
                {'id': 10, 'carrier': 1, 'driver': 5},
                {'carrier': 1, 'driver': 6},
            ]
        },
        request_only=True,
    ),
    OpenApiExample(
        'Leg Response',
        summary='Leg response with transformed structure',
        description='Response format with leg_id and load_id fields',
        value={
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
            'shipment_assignments': [
                {
                    'id': 10,
                    'carrier': 1,
                    'driver': 5,
                },
            ],
        },
        response_only=True,
    ),
]


SHIPMENT_ASSIGNMENT_SWAP_EXAMPLES = [
    OpenApiExample(
        'Swap Drivers Request',
        summary='Swap drivers between two legs',
        description='Simplified swap operation using leg_id and driver_id. '
                    'The carrier is automatically preserved from the original assignment.',
        value={
            'swap': [
                {'leg_id': 1, 'driver_id': 10},
                {'leg_id': 2, 'driver_id': 5},
            ]
        },
        request_only=True,
    ),
    OpenApiExample(
        'Swap Response',
        summary='Response after swap operation',
        description='Returns counts and details of deleted and created assignments.',
        value={
            'deleted_count': 2,
            'deleted_ids': [101, 102],
            'created_count': 2,
            'created': [
                {
                    'id': 201,
                    'carrier': {'id': 1, 'carrier_name': 'ABC Trucking'},
                    'driver': {'id': 10, 'full_name': 'John Smith'},
                },
                {
                    'id': 202,
                    'carrier': {'id': 1, 'carrier_name': 'ABC Trucking'},
                    'driver': {'id': 5, 'full_name': 'Jane Doe'},
                },
            ]
        },
        response_only=True,
    ),
]


SHIPMENT_ASSIGNMENT_BULK_DELETE_EXAMPLES = [
    OpenApiExample(
        'Bulk Delete Request',
        summary='Delete multiple assignments',
        description='Delete one or more shipment assignments by their IDs.',
        value={'ids': [1, 2, 3]},
        request_only=True,
    ),
    OpenApiExample(
        'Bulk Delete Response',
        summary='Response after bulk delete operation',
        description='Returns count and IDs of deleted assignments.',
        value={
            'deleted_count': 3,
            'deleted_ids': [1, 2, 3],
        },
        response_only=True,
    ),
]
