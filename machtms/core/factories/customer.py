import factory
from factory.django import DjangoModelFactory

from machtms.backend.customers.models import Customer, CustomerAP, CustomerRepresentative


class CustomerFactory(DjangoModelFactory):
    """Factory for creating Customer instances."""

    class Meta:
        model = Customer

    customer_name = factory.Faker('company')
    address = factory.SubFactory('machtms.core.factories.addresses.AddressFactory')
    phone_number = factory.Faker('numerify', text='###-###-####')


class CustomerAPFactory(DjangoModelFactory):
    """Factory for creating CustomerAP (Accounts Payable) instances."""

    class Meta:
        model = CustomerAP

    email = factory.Faker('company_email')
    phone_number = factory.Faker('numerify', text='###-###-####')
    payment_type = factory.Faker(
        'random_element',
        elements=[choice[0] for choice in CustomerAP.PaymentType.choices]
    )
    company = factory.SubFactory(CustomerFactory)


class CustomerRepresentativeFactory(DjangoModelFactory):
    """Factory for creating CustomerRepresentative instances."""

    class Meta:
        model = CustomerRepresentative

    name = factory.Faker('name')
    email = factory.Faker('email')
    phone_number = factory.Faker('numerify', text='###-###-####')
    company = factory.SubFactory(CustomerFactory)
