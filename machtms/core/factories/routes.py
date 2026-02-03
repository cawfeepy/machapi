import factory
from factory.django import DjangoModelFactory

from machtms.backend.routes.models import Stop


class StopFactory(DjangoModelFactory):
    """
    Factory for creating Stop instances in tests.

    Creates stops with realistic data for transportation routes,
    including proper foreign key relationships to Leg and Address.
    """

    class Meta:
        model = Stop

    leg = factory.SubFactory('machtms.core.factories.leg.LegFactory')
    stop_number = factory.Sequence(lambda n: n + 1)
    address = factory.SubFactory('machtms.core.factories.addresses.AddressFactory')

    start_range = factory.Faker('date_time_this_month', tzinfo=None)
    end_range = factory.Faker('date_time_this_month', tzinfo=None)

    action = factory.Faker(
        'random_element',
        elements=['LL', 'LU', 'HL', 'LD', 'EMPP', 'EMPD', 'HUBP', 'HUBD']
    )

    po_numbers = factory.Faker('bothify', text='PO-####-???')
    driver_notes = factory.Faker('sentence', nb_words=10)
