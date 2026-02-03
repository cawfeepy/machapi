import factory
from factory.django import DjangoModelFactory

from machtms.backend.loads.models import BillingStatus, Load, LoadStatus, TrailerType


class LoadFactory(DjangoModelFactory):
    """
    Factory for creating Load instances for testing purposes.
    """

    class Meta:
        model = Load

    reference_number = factory.Sequence(lambda n: f'REF-{n:06d}')
    bol_number = factory.Sequence(lambda n: f'BOL-{n:06d}')
    customer = factory.SubFactory('machtms.core.factories.customer.CustomerFactory')
    status = factory.Faker(
        'random_element',
        elements=[choice[0] for choice in LoadStatus.choices]
    )
    billing_status = factory.Faker(
        'random_element',
        elements=[choice[0] for choice in BillingStatus.choices]
    )
    trailer_type = factory.Faker(
        'random_element',
        elements=[choice[0] for choice in TrailerType.choices]
    )
