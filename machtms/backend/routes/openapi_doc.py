from drf_spectacular.utils import OpenApiExample


STOP_READ_EXAMPLES = [
    OpenApiExample(
        'Stop Response',
        summary='Full stop object in response',
        value={
            'id': 1,
            'leg': 1,
            'stop_number': 1,
            'address': 1,
            'start_range': '2024-01-15T08:00:00Z',
            'end_range': '2024-01-15T12:00:00Z',
            'timestamp': '2024-01-10T10:30:00Z',
            'action': 'LL',
            'po_numbers': 'PO-12345',
            'driver_notes': 'Dock 5, call on arrival',
        },
        response_only=True,
    ),
]

STOP_EXAMPLES = [
    OpenApiExample(
        'Create Stop Request',
        summary='Create a new stop within a leg',
        description='Request body for creating a stop. The leg field is set by the parent serializer.',
        value={
            'stop_number': 1,
            'address': 1,
            'start_range': '2024-01-15T08:00:00Z',
            'end_range': '2024-01-15T12:00:00Z',
            'action': 'LL',
            'po_numbers': 'PO-12345',
            'driver_notes': 'Dock 5, call on arrival',
        },
        request_only=True,
    ),
    OpenApiExample(
        'Update Stop Request',
        summary='Update existing stop with ID',
        description='Include the stop ID when updating an existing stop',
        value={
            'id': 1,
            'stop_number': 1,
            'address': 2,
            'start_range': '2024-01-15T09:00:00Z',
            'end_range': '2024-01-15T13:00:00Z',
            'action': 'LU',
            'po_numbers': 'PO-12345, PO-12346',
            'driver_notes': 'Updated: Use rear entrance',
        },
        request_only=True,
    ),
    OpenApiExample(
        'Stop Response',
        summary='Full stop object in response',
        value={
            'id': 1,
            'leg': 1,
            'stop_number': 1,
            'address': 1,
            'start_range': '2024-01-15T08:00:00Z',
            'end_range': '2024-01-15T12:00:00Z',
            'timestamp': '2024-01-10T10:30:00Z',
            'action': 'LL',
            'po_numbers': 'PO-12345',
            'driver_notes': 'Dock 5, call on arrival',
        },
        response_only=True,
    ),
]

STOP_WRITE_EXAMPLES = [
    OpenApiExample(
        'Stop Write Request',
        summary='Minimal stop data for nested creation',
        value={
            'action': 'LL',
            'address': 1,
        },
        request_only=True,
    ),
    OpenApiExample(
        'Stop Update Request',
        summary='Update existing stop with ID',
        value={
            'id': 1,
            'action': 'LU',
            'address': 2,
        },
        request_only=True,
    ),
]
