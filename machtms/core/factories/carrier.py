import factory
from factory.django import DjangoModelFactory

from machtms.backend.carriers.models import Carrier, Driver


class CarrierFactory(DjangoModelFactory):
    """
    Factory for creating Carrier instances.
    """
    class Meta:
        model = Carrier

    carrier_name = factory.Faker('company')
    phone = factory.Faker('numerify', text='###-###-####')
    email = factory.Faker('company_email')
    contractor = factory.Faker('boolean')


class DriverFactory(DjangoModelFactory):
    """
    Factory for creating Driver instances.
    """
    class Meta:
        model = Driver

    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    phone_number = factory.Faker('numerify', text='###-###-####')
    email = factory.Faker('email')
    address = factory.SubFactory('machtms.core.factories.addresses.AddressFactory')
    carrier = factory.SubFactory(CarrierFactory)
