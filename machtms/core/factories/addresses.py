import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from machtms.backend.addresses.models import (
    Address,
    AddressUsageAccumulate,
    AddressUsageByCustomerAccumulate,
)


class AddressFactory(DjangoModelFactory):
    """Factory for creating Address instances."""

    class Meta:
        model = Address

    street = factory.Faker('street_address')
    city = factory.Faker('city')
    state = factory.Faker('state_abbr')
    zip_code = factory.Faker('zipcode')
    country = factory.Faker('country')
    latitude = factory.Faker('latitude')
    longitude = factory.Faker('longitude')


class AddressUsageAccumulateFactory(DjangoModelFactory):
    """Factory for creating AddressUsageAccumulate instances."""

    class Meta:
        model = AddressUsageAccumulate

    address = factory.SubFactory(AddressFactory)
    last_used = factory.LazyFunction(timezone.now)


class AddressUsageByCustomerAccumulateFactory(DjangoModelFactory):
    """Factory for creating AddressUsageByCustomerAccumulate instances."""

    class Meta:
        model = AddressUsageByCustomerAccumulate

    address = factory.SubFactory(AddressFactory)
    customer = factory.SubFactory('machtms.core.factories.customer.CustomerFactory')
    last_used = factory.LazyFunction(timezone.now)
