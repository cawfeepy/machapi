from django.test import TestCase

from machtms.backend.customers.models import Customer
from machtms.backend.addresses.models import CustomerAddress
from machtms.backend.auth.models import Organization
from machtms.core.factories import CustomerFactory, CustomerAddressFactory


class CustomerFactoryTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(company_name="Test Org")

    def test_customer_factory_creates_customer_address(self):
        customer = CustomerFactory.create(organization=self.org)
        self.assertIsNotNone(customer.address)
        self.assertIsInstance(customer.address, CustomerAddress)

    def test_customer_address_optional(self):
        customer = Customer.objects.create(
            organization=self.org,
            customer_name="No Address Customer",
            address=None,
        )
        self.assertIsNone(customer.address)
