from django.test import TestCase

from machtms.backend.addresses.models import Address, CustomerAddress, CarrierAddress
from machtms.backend.auth.models import Organization
from machtms.core.factories import AddressFactory, CustomerAddressFactory, CarrierAddressFactory


class CustomerAddressModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(company_name="Test Org")

    def test_create_customer_address(self):
        addr = CustomerAddressFactory.create(organization=self.org)
        self.assertIsNotNone(addr.pk)
        self.assertTrue(addr.street)
        self.assertTrue(addr.city)
        self.assertTrue(addr.state)

    def test_customer_address_fields(self):
        addr = CustomerAddress.objects.create(
            organization=self.org,
            street="123 Main St",
            city="Dallas",
            state="TX",
            zip_code="75201",
            country="US",
        )
        addr.refresh_from_db()
        self.assertEqual(addr.street, "123 Main St")
        self.assertEqual(addr.city, "Dallas")
        self.assertEqual(addr.state, "TX")
        self.assertEqual(addr.zip_code, "75201")
        self.assertEqual(addr.country, "US")


class CarrierAddressModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(company_name="Test Org")

    def test_create_carrier_address(self):
        addr = CarrierAddressFactory.create(organization=self.org)
        self.assertIsNotNone(addr.pk)
        self.assertTrue(addr.street)
        self.assertTrue(addr.city)

    def test_carrier_address_fields(self):
        addr = CarrierAddress.objects.create(
            organization=self.org,
            street="456 Carrier Blvd",
            city="Houston",
            state="TX",
            zip_code="77001",
            country="US",
        )
        addr.refresh_from_db()
        self.assertEqual(addr.street, "456 Carrier Blvd")
        self.assertEqual(addr.city, "Houston")


class AddressPlaceNameTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(company_name="Test Org")

    def test_address_factory_has_place_name(self):
        addr = AddressFactory.create(organization=self.org)
        self.assertIsNotNone(addr.place_name)
        self.assertTrue(addr.place_name)

    def test_address_str_includes_place_name(self):
        addr = Address.objects.create(
            organization=self.org,
            place_name="Amazon Warehouse",
            street="100 Fulfillment Dr",
            city="Phoenix",
            state="AZ",
            zip_code="85001",
            country="US",
        )
        self.assertIn("Amazon Warehouse", str(addr))
