from django.test import TestCase

from machtms.backend.carriers.models import Carrier
from machtms.backend.addresses.models import CarrierAddress
from machtms.backend.auth.models import Organization
from machtms.core.factories import CarrierFactory, CarrierAddressFactory


class CarrierFactoryTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(company_name="Test Org")

    def test_carrier_factory_creates_address(self):
        carrier = CarrierFactory.create(organization=self.org)
        self.assertIsNotNone(carrier.address)
        self.assertIsInstance(carrier.address, CarrierAddress)

    def test_carrier_factory_has_mc_and_usdot(self):
        carrier = CarrierFactory.create(organization=self.org)
        self.assertIsNotNone(carrier.mc)
        self.assertIsNotNone(carrier.usdot)
        self.assertTrue(carrier.mc)
        self.assertTrue(carrier.usdot)

    def test_carrier_address_optional(self):
        carrier = Carrier.objects.create(
            organization=self.org,
            carrier_name="No Address Carrier",
            address=None,
        )
        self.assertIsNone(carrier.address)

    def test_carrier_mc_usdot_optional(self):
        carrier = Carrier.objects.create(
            organization=self.org,
            carrier_name="Minimal Carrier",
        )
        self.assertEqual(carrier.mc, "")
        self.assertEqual(carrier.usdot, "")
