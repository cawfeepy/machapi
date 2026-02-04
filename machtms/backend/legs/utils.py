from django.db import transaction

from machtms.backend.carriers.models import Driver
from machtms.backend.legs.models import ShipmentAssignment


def swap_shipment_assignment(swap_data: list[dict], organization) -> dict:
    """
    Swap drivers between legs by deleting old assignments and creating new ones.

    The carrier is determined from each driver's carrier relationship.

    Args:
        swap_data: List of dicts, e.g. [{'leg_id': 1, 'driver_id': 2}, ...]
        organization: Organization instance or ID

    Returns:
        dict with 'deleted_ids', 'deleted_count', 'created', 'created_count'
    """
    organization_id = organization.id if hasattr(organization, 'id') else organization

    leg_ids = [item['leg_id'] for item in swap_data]
    driver_ids = [item['driver_id'] for item in swap_data]

    # Fetch drivers to get their carriers
    drivers = Driver.objects.filter(id__in=driver_ids).select_related('carrier')
    driver_map = {d.id: d for d in drivers}

    # Find existing assignments to delete
    existing = ShipmentAssignment.objects.filter(
        leg_id__in=leg_ids,
        organization_id=organization_id
    )
    deleted_ids = list(existing.values_list('id', flat=True))

    with transaction.atomic():
        # Delete old assignments
        existing.delete()

        # Create new assignments
        created = []
        for item in swap_data:
            driver = driver_map.get(item['driver_id'])
            if not driver:
                raise ValueError(f"Driver with id {item['driver_id']} not found")

            assignment = ShipmentAssignment.objects.create(
                leg_id=item['leg_id'],
                driver_id=driver.id,
                carrier_id=driver.carrier_id,
                organization_id=organization_id
            )
            created.append(assignment)

    return {
        'deleted_ids': deleted_ids,
        'deleted_count': len(deleted_ids),
        'created': created,
        'created_count': len(created),
    }
