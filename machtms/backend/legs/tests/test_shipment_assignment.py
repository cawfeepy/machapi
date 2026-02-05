"""
Test suite for the ShipmentAssignment endpoints.

This module contains comprehensive tests for:
1. Swap endpoint
2. Bulk delete endpoint
3. Nested shipment_assignment in LegSerializer
4. Validation errors
5. Organization isolation
"""
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from machtms.backend.auth.models import Organization, OrganizationUser, UserProfile
from machtms.backend.legs.models import Leg, ShipmentAssignment
from machtms.backend.loads.models import Load
from machtms.backend.carriers.models import Carrier, Driver
from machtms.backend.customers.models import Customer
from machtms.core.factories import (
    CarrierFactory,
    CustomerFactory,
    DriverFactory,
    LegFactory,
    LoadFactory,
    ShipmentAssignmentFactory,
)
from machtms.core.testing import OrganizationAPITestCase


@override_settings(DEBUG=False)
class ShipmentAssignmentTests(OrganizationAPITestCase):
    """
    Tests for shipment_assignment field in LegSerializer.

    Each leg can have at most one shipment assignment (OneToOneField).
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data that will be shared across all test methods."""
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-123-4567",
            email="test@testorg.com"
        )
        cls.user = OrganizationUser.objects.create_user(
            email="testuser@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User"
        )
        cls.user_profile = UserProfile.objects.create(
            user=cls.user,
            organization=cls.organization
        )

        cls.customer = CustomerFactory.create(organization=cls.organization)
        cls.carrier = CarrierFactory.create(organization=cls.organization)
        cls.other_carrier = CarrierFactory.create(organization=cls.organization)

        cls.driver1 = DriverFactory.create(carrier=cls.carrier, organization=cls.organization)
        cls.driver2 = DriverFactory.create(carrier=cls.carrier, organization=cls.organization)
        cls.other_driver = DriverFactory.create(
            carrier=cls.other_carrier,
            organization=cls.organization
        )

    def setUp(self):
        """Set up test fixtures for each test method."""
        self.authenticate(self.user, self.organization)

        self.load = LoadFactory.create(customer=self.customer, organization=self.organization)
        self.leg = LegFactory.create(load=self.load, organization=self.organization)

        self.load_url = reverse('load-detail', kwargs={'pk': self.load.id})

    def test_create_leg_with_shipment_assignment(self):
        """
        Test creating a new leg with shipment_assignment via Load update.
        """
        payload = {
            'legs': [
                {
                    'shipment_assignment': {'carrier': self.carrier.id, 'driver': self.driver1.id},
                }
            ]
        }

        response = self.client.patch(self.load_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify the leg was created with the assignment
        self.load.refresh_from_db()
        legs = list(self.load.legs.all())
        self.assertEqual(len(legs), 1)

        assignment = legs[0].shipment_assignment
        self.assertEqual(assignment.carrier_id, self.carrier.id)
        self.assertEqual(assignment.driver_id, self.driver1.id)

    def test_update_leg_shipment_assignment(self):
        """
        Test updating an existing shipment assignment on a leg.
        """
        existing_assignment = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver1,
            leg=self.leg,
            organization=self.organization
        )

        payload = {
            'legs': [
                {
                    'id': self.leg.id,
                    'shipment_assignment': {
                        'id': existing_assignment.id,
                        'carrier': self.carrier.id,
                        'driver': self.driver2.id
                    },
                }
            ]
        }

        response = self.client.patch(self.load_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        existing_assignment.refresh_from_db()
        self.assertEqual(existing_assignment.driver_id, self.driver2.id)

    def test_remove_shipment_assignment_with_null(self):
        """
        Test removing shipment assignment by sending null.
        """
        ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver1,
            leg=self.leg,
            organization=self.organization
        )

        payload = {
            'legs': [
                {
                    'id': self.leg.id,
                    'shipment_assignment': None
                }
            ]
        }

        response = self.client.patch(self.load_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.leg.refresh_from_db()
        self.assertFalse(hasattr(self.leg, 'shipment_assignment') and self.leg.shipment_assignment is not None)

    def test_update_leg_without_shipment_assignment_field(self):
        """
        Test that omitting shipment_assignment field leaves existing assignment unchanged.
        """
        existing_assignment = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver1,
            leg=self.leg,
            organization=self.organization
        )

        payload = {
            'legs': [
                {
                    'id': self.leg.id,
                }
            ]
        }

        response = self.client.patch(self.load_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertTrue(
            ShipmentAssignment.objects.filter(id=existing_assignment.id).exists()
        )

    def test_validation_driver_must_belong_to_carrier(self):
        """
        Test that driver must belong to the specified carrier.
        """
        payload = {
            'legs': [
                {
                    'shipment_assignment': {'carrier': self.carrier.id, 'driver': self.other_driver.id},
                }
            ]
        }

        response = self.client.patch(self.load_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('driver', str(response.data).lower())

    def test_response_contains_shipment_assignment(self):
        """
        Test that response includes shipment_assignment in legs.
        """
        ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver1,
            leg=self.leg,
            organization=self.organization
        )

        response = self.client.get(self.load_url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        legs = response.data.get('legs', [])
        self.assertGreater(len(legs), 0)

        leg_data = legs[0]
        self.assertIn('shipment_assignment', leg_data)
        self.assertIsNotNone(leg_data['shipment_assignment'])
        self.assertEqual(
            leg_data['shipment_assignment']['carrier'],
            self.carrier.id
        )
        self.assertEqual(
            leg_data['shipment_assignment']['driver'],
            self.driver1.id
        )

    def test_response_shipment_assignment_is_null_when_unassigned(self):
        """
        Test that shipment_assignment is null when leg has no assignment.
        """
        response = self.client.get(self.load_url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        legs = response.data.get('legs', [])
        self.assertGreater(len(legs), 0)

        leg_data = legs[0]
        self.assertIn('shipment_assignment', leg_data)
        self.assertIsNone(leg_data['shipment_assignment'])


@override_settings(DEBUG=False)
class ShipmentAssignmentSwapTests(OrganizationAPITestCase):
    """
    Tests for the ShipmentAssignment swap endpoint.

    The swap endpoint provides a simplified interface for swapping drivers
    between two legs, preserving carriers from original assignments.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data that will be shared across all test methods."""
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-123-4567",
            email="test@testorg.com"
        )
        cls.other_organization = Organization.objects.create(
            company_name="Other Org",
            phone="555-987-6543",
            email="other@testorg.com"
        )

        cls.user = OrganizationUser.objects.create_user(
            email="testuser@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User"
        )
        cls.user_profile = UserProfile.objects.create(
            user=cls.user,
            organization=cls.organization
        )

        cls.customer = CustomerFactory.create(organization=cls.organization)
        cls.carrier = CarrierFactory.create(organization=cls.organization)

        cls.driver1 = DriverFactory.create(carrier=cls.carrier, organization=cls.organization)
        cls.driver2 = DriverFactory.create(carrier=cls.carrier, organization=cls.organization)

    def setUp(self):
        """Set up test fixtures for each test method."""
        self.authenticate(self.user, self.organization)

        self.load1 = LoadFactory.create(customer=self.customer, organization=self.organization)
        self.load2 = LoadFactory.create(customer=self.customer, organization=self.organization)

        self.leg1 = LegFactory.create(load=self.load1, organization=self.organization)
        self.leg2 = LegFactory.create(load=self.load2, organization=self.organization)

        self.assignment1 = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver1,
            leg=self.leg1,
            organization=self.organization
        )
        self.assignment2 = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver2,
            leg=self.leg2,
            organization=self.organization
        )

        self.swap_url = reverse('shipment-assignment-swap')

    def test_swap_success(self):
        """
        Test swapping drivers between two legs.

        Should delete original assignments and create new ones with swapped drivers.
        """
        payload = {
            'swap': [
                {'leg_id': self.leg1.id, 'driver_id': self.driver2.id},
                {'leg_id': self.leg2.id, 'driver_id': self.driver1.id},
            ]
        }

        response = self.client.post(self.swap_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 2)
        self.assertEqual(set(response.data['deleted_ids']), {self.assignment1.id, self.assignment2.id})
        self.assertEqual(response.data['created_count'], 2)
        self.assertEqual(len(response.data['created']), 2)

        self.assertFalse(ShipmentAssignment.objects.filter(id=self.assignment1.id).exists())
        self.assertFalse(ShipmentAssignment.objects.filter(id=self.assignment2.id).exists())

        new_leg1_assignment = ShipmentAssignment.objects.get(leg=self.leg1)
        new_leg2_assignment = ShipmentAssignment.objects.get(leg=self.leg2)
        self.assertEqual(new_leg1_assignment.driver_id, self.driver2.id)
        self.assertEqual(new_leg2_assignment.driver_id, self.driver1.id)

    def test_swap_requires_exactly_2_items(self):
        """
        Test that swap operation requires exactly 2 items.
        """
        payload = {
            'swap': [
                {'leg_id': self.leg1.id, 'driver_id': self.driver2.id},
            ]
        }

        response = self.client.post(self.swap_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('swap', response.data)
        self.assertIn('exactly 2', str(response.data['swap']))

    def test_swap_nonexistent_leg(self):
        """
        Test that swap with non-existent leg returns validation error.
        """
        payload = {
            'swap': [
                {'leg_id': 99999, 'driver_id': self.driver2.id},
                {'leg_id': self.leg2.id, 'driver_id': self.driver1.id},
            ]
        }

        response = self.client.post(self.swap_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_swap_with_missing_assignment(self):
        """
        Test swap when one leg has no existing assignment.

        Both assignments are created since carrier comes from the driver.
        """
        self.assignment1.delete()

        payload = {
            'swap': [
                {'leg_id': self.leg1.id, 'driver_id': self.driver2.id},
                {'leg_id': self.leg2.id, 'driver_id': self.driver1.id},
            ]
        }

        response = self.client.post(self.swap_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only 1 existed to delete, but 2 are created (carrier from driver)
        self.assertEqual(response.data['deleted_count'], 1)
        self.assertEqual(response.data['created_count'], 2)

        # Both legs should have assignments
        new_leg1_assignment = ShipmentAssignment.objects.get(leg=self.leg1)
        new_leg2_assignment = ShipmentAssignment.objects.get(leg=self.leg2)

        self.assertEqual(new_leg1_assignment.driver_id, self.driver2.id)
        self.assertEqual(new_leg2_assignment.driver_id, self.driver1.id)

    def test_swap_uses_driver_carrier(self):
        """
        Test that swap uses the carrier from the driver.
        """
        payload = {
            'swap': [
                {'leg_id': self.leg1.id, 'driver_id': self.driver2.id},
                {'leg_id': self.leg2.id, 'driver_id': self.driver1.id},
            ]
        }

        response = self.client.post(self.swap_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_leg1_assignment = ShipmentAssignment.objects.get(leg=self.leg1)
        new_leg2_assignment = ShipmentAssignment.objects.get(leg=self.leg2)

        self.assertEqual(new_leg1_assignment.carrier_id, self.carrier.id)
        self.assertEqual(new_leg2_assignment.carrier_id, self.carrier.id)


@override_settings(DEBUG=False)
class ShipmentAssignmentBulkDeleteTests(OrganizationAPITestCase):
    """
    Tests for the ShipmentAssignment bulk delete endpoint.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data that will be shared across all test methods."""
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-123-4567",
            email="test@testorg.com"
        )
        cls.other_organization = Organization.objects.create(
            company_name="Other Org",
            phone="555-987-6543",
            email="other@testorg.com"
        )

        cls.user = OrganizationUser.objects.create_user(
            email="testuser@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User"
        )
        cls.user_profile = UserProfile.objects.create(
            user=cls.user,
            organization=cls.organization
        )

        cls.customer = CustomerFactory.create(organization=cls.organization)
        cls.carrier = CarrierFactory.create(organization=cls.organization)

        cls.driver1 = DriverFactory.create(carrier=cls.carrier, organization=cls.organization)
        cls.driver2 = DriverFactory.create(carrier=cls.carrier, organization=cls.organization)
        cls.driver3 = DriverFactory.create(carrier=cls.carrier, organization=cls.organization)

    def setUp(self):
        """Set up test fixtures for each test method."""
        self.authenticate(self.user, self.organization)

        self.load = LoadFactory.create(customer=self.customer, organization=self.organization)

        self.leg1 = LegFactory.create(load=self.load, organization=self.organization)
        self.leg2 = LegFactory.create(load=self.load, organization=self.organization)
        self.leg3 = LegFactory.create(load=self.load, organization=self.organization)

        self.assignment1 = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver1,
            leg=self.leg1,
            organization=self.organization
        )
        self.assignment2 = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver2,
            leg=self.leg2,
            organization=self.organization
        )
        self.assignment3 = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver3,
            leg=self.leg3,
            organization=self.organization
        )

        self.bulk_delete_url = reverse('shipment-assignment-bulk-delete')

    def test_bulk_delete_success(self):
        """
        Test deleting multiple assignments at once.
        """
        payload = {
            'ids': [self.assignment1.id, self.assignment2.id]
        }

        response = self.client.post(self.bulk_delete_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 2)
        self.assertEqual(set(response.data['deleted_ids']), {self.assignment1.id, self.assignment2.id})

        self.assertFalse(ShipmentAssignment.objects.filter(id=self.assignment1.id).exists())
        self.assertFalse(ShipmentAssignment.objects.filter(id=self.assignment2.id).exists())
        self.assertTrue(ShipmentAssignment.objects.filter(id=self.assignment3.id).exists())

    def test_bulk_delete_empty_ids(self):
        """
        Test that empty ids list returns validation error.
        """
        payload = {
            'ids': []
        }

        response = self.client.post(self.bulk_delete_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ids', response.data)

    def test_bulk_delete_nonexistent_id(self):
        """
        Test that non-existent ID returns validation error.
        """
        payload = {
            'ids': [99999]
        }

        response = self.client.post(self.bulk_delete_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_delete_other_organization(self):
        """
        Test that assignment from another organization returns validation error.
        """
        other_customer = CustomerFactory.create(organization=self.other_organization)
        other_carrier = CarrierFactory.create(organization=self.other_organization)
        other_driver = DriverFactory.create(
            carrier=other_carrier,
            organization=self.other_organization
        )
        other_load = LoadFactory.create(
            customer=other_customer,
            organization=self.other_organization
        )
        other_leg = LegFactory.create(
            load=other_load,
            organization=self.other_organization
        )
        other_assignment = ShipmentAssignmentFactory.create(
            carrier=other_carrier,
            driver=other_driver,
            leg=other_leg,
            organization=self.other_organization
        )

        payload = {
            'ids': [other_assignment.id]
        }

        response = self.client.post(self.bulk_delete_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertTrue(ShipmentAssignment.objects.filter(id=other_assignment.id).exists())

    def test_bulk_delete_single_assignment(self):
        """
        Test deleting a single assignment.
        """
        payload = {
            'ids': [self.assignment1.id]
        }

        response = self.client.post(self.bulk_delete_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 1)
        self.assertEqual(response.data['deleted_ids'], [self.assignment1.id])

        self.assertFalse(ShipmentAssignment.objects.filter(id=self.assignment1.id).exists())
