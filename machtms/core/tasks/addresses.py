import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def update_address_usage(self, stop_id: int, address_id: int):
    """
    Create address usage accumulation records for a stop.

    Args:
        stop_id: ID of the stop (for customer lookup)
        address_id: ID of the address being used
    """
    from machtms.backend.routes.models import Stop
    from machtms.backend.addresses.models import (
        AddressUsageAccumulate,
        AddressUsageByCustomerAccumulate,
    )

    try:
        stop = Stop.objects.select_related('leg__load__customer').get(pk=stop_id)
    except Stop.DoesNotExist:
        logger.warning(f"Stop {stop_id} not found for address usage update")
        return

    # Create general usage record
    AddressUsageAccumulate.objects.create(
        address_id=address_id,
        last_used=timezone.now(),
    )

    # Create customer-specific record if load has a customer
    # Safely traverse the relationship chain
    leg = getattr(stop, 'leg', None)
    load = getattr(leg, 'load', None) if leg else None
    customer_id = getattr(load, 'customer_id', None) if load else None

    if customer_id:
        AddressUsageByCustomerAccumulate.objects.create(
            address_id=address_id,
            customer_id=customer_id,
            last_used=timezone.now(),
        )

    logger.info(f"Updated address usage for stop={stop_id}, address={address_id}")
