"""
Test suite for the ShipmentAssignment modify endpoint.

This module contains comprehensive tests for:
1. Swap operation (2 deletes, 2 adds)
2. Unassign operation (delete only)
3. Assign operation (add only)
4. Validation errors
5. Atomicity (rollback on failure)
6. Organization isolation
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
class ShipmentAssignmentModifyTests(OrganizationAPITestCase):
    """
    Tests for the ShipmentAssignment modify endpoint.

    The modify endpoint supports three operations:
    - Swap: Delete 2 assignments and create 2 new ones
    - Unassign: Delete assignments without creating new ones
    - Assign: Create new assignments without deleting
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

        self.load1 = LoadFactory.create(customer=self.customer, organization=self.organization)
        self.load2 = LoadFactory.create(customer=self.customer, organization=self.organization)

        self.leg1 = LegFactory.create(load=self.load1, organization=self.organization)
        self.leg2 = LegFactory.create(load=self.load2, organization=self.organization)
        self.leg3 = LegFactory.create(load=self.load1, organization=self.organization)

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

        self.modify_url = reverse('shipment-assignment-modify')

    def test_swap_operation_success(self):
        """
        Test swapping drivers between two legs.

        Swap requires exactly 2 deletions and 2 additions.
        """
        payload = {
            'to_delete': [self.assignment1.id, self.assignment2.id],
            'to_add': [
                {'carrier': self.carrier.id, 'driver': self.driver2.id, 'leg': self.leg1.id},
                {'carrier': self.carrier.id, 'driver': self.driver1.id, 'leg': self.leg2.id},
            ]
        }

        response = self.client.post(self.modify_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 2)
        self.assertEqual(set(response.data['deleted_ids']), {self.assignment1.id, self.assignment2.id})
        self.assertEqual(response.data['created_count'], 2)
        self.assertEqual(len(response.data['created']), 2)

        self.assertFalse(ShipmentAssignment.objects.filter(id=self.assignment1.id).exists())
        self.assertFalse(ShipmentAssignment.objects.filter(id=self.assignment2.id).exists())

        new_assignments = ShipmentAssignment.objects.filter(leg__in=[self.leg1, self.leg2])
        self.assertEqual(new_assignments.count(), 2)

    def test_unassign_operation_success(self):
        """
        Test removing driver assignments without reassigning.
        """
        payload = {
            'to_delete': [self.assignment1.id],
            'to_add': []
        }

        response = self.client.post(self.modify_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 1)
        self.assertEqual(response.data['deleted_ids'], [self.assignment1.id])
        self.assertEqual(response.data['created_count'], 0)
        self.assertEqual(response.data['created'], [])

        self.assertFalse(ShipmentAssignment.objects.filter(id=self.assignment1.id).exists())
        self.assertTrue(ShipmentAssignment.objects.filter(id=self.assignment2.id).exists())

    def test_assign_operation_success(self):
        """
        Test creating new driver assignments without deleting existing ones.
        """
        payload = {
            'to_delete': [],
            'to_add': [
                {'carrier': self.carrier.id, 'driver': self.driver3.id, 'leg': self.leg3.id},
            ]
        }

        response = self.client.post(self.modify_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 0)
        self.assertEqual(response.data['deleted_ids'], [])
        self.assertEqual(response.data['created_count'], 1)
        self.assertEqual(len(response.data['created']), 1)

        self.assertTrue(ShipmentAssignment.objects.filter(id=self.assignment1.id).exists())
        self.assertTrue(ShipmentAssignment.objects.filter(id=self.assignment2.id).exists())

        new_assignment = ShipmentAssignment.objects.filter(leg=self.leg3).first()
        self.assertIsNotNone(new_assignment)
        self.assertEqual(new_assignment.driver, self.driver3)

    def test_empty_payload_validation_error(self):
        """
        Test that empty payload returns validation error.
        """
        payload = {
            'to_delete': [],
            'to_add': []
        }

        response = self.client.post(self.modify_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('At least one of to_delete or to_add must be provided', str(response.data))

    def test_swap_with_wrong_delete_count_validation_error(self):
        """
        Test that swap operation with wrong delete count fails validation.

        Swap operations require exactly 2 items in to_delete.
        """
        payload = {
            'to_delete': [self.assignment1.id],
            'to_add': [
                {'carrier': self.carrier.id, 'driver': self.driver2.id, 'leg': self.leg1.id},
                {'carrier': self.carrier.id, 'driver': self.driver1.id, 'leg': self.leg2.id},
            ]
        }

        response = self.client.post(self.modify_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('to_delete', response.data)
        self.assertIn('exactly 2', str(response.data['to_delete']))

    def test_swap_with_wrong_add_count_validation_error(self):
        """
        Test that swap operation with wrong add count fails validation.

        Swap operations require exactly 2 items in to_add.
        """
        payload = {
            'to_delete': [self.assignment1.id, self.assignment2.id],
            'to_add': [
                {'carrier': self.carrier.id, 'driver': self.driver2.id, 'leg': self.leg1.id},
            ]
        }

        response = self.client.post(self.modify_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('to_add', response.data)
        self.assertIn('exactly 2', str(response.data['to_add']))

    def test_nonexistent_assignment_id_validation_error(self):
        """
        Test that non-existent assignment ID returns validation error.
        """
        nonexistent_id = 99999
        payload = {
            'to_delete': [nonexistent_id],
            'to_add': []
        }

        response = self.client.post(self.modify_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('to_delete', response.data)

    def test_other_organization_assignment_validation_error(self):
        """
        Test that assignment from another organization returns validation error.

        Users should not be able to delete assignments from other organizations.
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
            'to_delete': [other_assignment.id],
            'to_add': []
        }

        response = self.client.post(self.modify_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('to_delete', response.data)

        self.assertTrue(ShipmentAssignment.objects.filter(id=other_assignment.id).exists())

    def test_atomicity_rollback_on_create_failure(self):
        """
        Test that if create fails, deletes are rolled back.

        Uses an invalid leg ID that will fail during creation.
        """
        initial_count = ShipmentAssignment.objects.filter(
            organization=self.organization
        ).count()

        payload = {
            'to_delete': [self.assignment1.id],
            'to_add': [
                {'carrier': self.carrier.id, 'driver': self.driver2.id, 'leg': 99999},
            ]
        }

        response = self.client.post(self.modify_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertTrue(ShipmentAssignment.objects.filter(id=self.assignment1.id).exists())
        self.assertEqual(
            ShipmentAssignment.objects.filter(organization=self.organization).count(),
            initial_count
        )

    def test_response_contains_full_created_assignment_data(self):
        """
        Test that response contains full nested data for created assignments.
        """
        payload = {
            'to_delete': [],
            'to_add': [
                {'carrier': self.carrier.id, 'driver': self.driver3.id, 'leg': self.leg3.id},
            ]
        }

        response = self.client.post(self.modify_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        created = response.data['created'][0]
        self.assertIn('id', created)
        self.assertIn('carrier', created)
        self.assertIn('driver', created)

        self.assertIsInstance(created['carrier'], dict)
        self.assertEqual(created['carrier']['id'], self.carrier.id)
        self.assertIn('carrier_name', created['carrier'])

        self.assertIsInstance(created['driver'], dict)
        self.assertEqual(created['driver']['id'], self.driver3.id)

    def test_unassign_multiple_assignments(self):
        """
        Test unassigning multiple assignments at once.
        """
        payload = {
            'to_delete': [self.assignment1.id, self.assignment2.id],
            'to_add': []
        }

        response = self.client.post(self.modify_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 2)
        self.assertEqual(set(response.data['deleted_ids']), {self.assignment1.id, self.assignment2.id})

        self.assertFalse(ShipmentAssignment.objects.filter(id=self.assignment1.id).exists())
        self.assertFalse(ShipmentAssignment.objects.filter(id=self.assignment2.id).exists())


@override_settings(DEBUG=True)
class ShipmentAssignmentModifyDebugModeTests(OrganizationAPITestCase):
    """
    Tests for the modify endpoint in DEBUG mode.

    In DEBUG mode, organization filtering is relaxed.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
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
        cls.driver = DriverFactory.create(carrier=cls.carrier, organization=cls.organization)

    def setUp(self):
        """Set up test fixtures."""
        self.authenticate(self.user, self.organization)

        self.load = LoadFactory.create(customer=self.customer, organization=self.organization)
        self.leg = LegFactory.create(load=self.load, organization=self.organization)
        self.assignment = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver,
            leg=self.leg,
            organization=self.organization
        )

        self.modify_url = reverse('shipment-assignment-modify')

    def test_basic_unassign_in_debug_mode(self):
        """
        Test basic unassign operation works in debug mode.
        """
        payload = {
            'to_delete': [self.assignment.id],
            'to_add': []
        }

        response = self.client.post(self.modify_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 1)
        self.assertFalse(ShipmentAssignment.objects.filter(id=self.assignment.id).exists())


@override_settings(DEBUG=False)
class NestedShipmentAssignmentTests(OrganizationAPITestCase):
    """
    Tests for nested shipment_assignments in LegSerializer.

    The LegSerializer supports nested writable shipment_assignments
    following the AutoNestedMixin pattern used for stops. This enables
    creating/updating legs with shipment assignments in a single request.
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
        cls.driver3 = DriverFactory.create(carrier=cls.carrier, organization=cls.organization)
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

    def test_create_leg_with_nested_shipment_assignments(self):
        """
        Test creating a new leg with nested shipment_assignments via Load update.

        Shipment assignments should be created and linked to the leg.
        """
        payload = {
            'legs': [
                {
                    'shipment_assignments': [
                        {'carrier': self.carrier.id, 'driver': self.driver1.id},
                    ]
                }
            ]
        }

        response = self.client.patch(self.load_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify the leg was created with the assignment
        self.load.refresh_from_db()
        legs = list(self.load.legs.all())
        self.assertEqual(len(legs), 1)

        assignments = legs[0].shipment_assignments.all()
        self.assertEqual(assignments.count(), 1)
        self.assertEqual(assignments[0].carrier_id, self.carrier.id)
        self.assertEqual(assignments[0].driver_id, self.driver1.id)

    def test_create_leg_with_multiple_shipment_assignments(self):
        """
        Test creating a leg with multiple shipment assignments.
        """
        payload = {
            'legs': [
                {
                    'shipment_assignments': [
                        {'carrier': self.carrier.id, 'driver': self.driver1.id},
                        {'carrier': self.carrier.id, 'driver': self.driver2.id},
                    ]
                }
            ]
        }

        response = self.client.patch(self.load_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.load.refresh_from_db()
        legs = list(self.load.legs.all())
        assignments = legs[0].shipment_assignments.all()
        self.assertEqual(assignments.count(), 2)

    def test_update_leg_add_shipment_assignment(self):
        """
        Test adding a new shipment assignment to an existing leg.
        """
        # First create an assignment
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
                    'shipment_assignments': [
                        {'id': existing_assignment.id, 'carrier': self.carrier.id, 'driver': self.driver1.id},
                        {'carrier': self.carrier.id, 'driver': self.driver2.id},
                    ]
                }
            ]
        }

        response = self.client.patch(self.load_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.leg.refresh_from_db()
        assignments = self.leg.shipment_assignments.all()
        self.assertEqual(assignments.count(), 2)

    def test_update_leg_remove_shipment_assignment(self):
        """
        Test removing shipment assignments by sending empty array.

        Sending an empty array for shipment_assignments should delete
        all existing assignments on the leg.
        """
        # Create assignments first
        ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver1,
            leg=self.leg,
            organization=self.organization
        )
        ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver2,
            leg=self.leg,
            organization=self.organization
        )
        self.assertEqual(self.leg.shipment_assignments.count(), 2)

        payload = {
            'legs': [
                {
                    'id': self.leg.id,
                    'shipment_assignments': []
                }
            ]
        }

        response = self.client.patch(self.load_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.leg.refresh_from_db()
        self.assertEqual(self.leg.shipment_assignments.count(), 0)

    def test_update_leg_without_shipment_assignments_field(self):
        """
        Test that omitting shipment_assignments field leaves existing assignments unchanged.
        """
        existing_assignment = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver1,
            leg=self.leg,
            organization=self.organization
        )

        # Update leg without shipment_assignments field
        payload = {
            'legs': [
                {
                    'id': self.leg.id,
                }
            ]
        }

        response = self.client.patch(self.load_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Existing assignment should still exist
        self.assertTrue(
            ShipmentAssignment.objects.filter(id=existing_assignment.id).exists()
        )

    def test_upsert_shipment_assignments(self):
        """
        Test upserting shipment assignments (update existing, add new, delete missing).

        Items with ID are updated, items without ID are created.
        Existing items not included in payload are deleted.
        """
        # Create two existing assignments
        assignment1 = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver1,
            leg=self.leg,
            organization=self.organization
        )
        assignment2 = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver2,
            leg=self.leg,
            organization=self.organization
        )

        # Payload updates assignment1, creates new, and omits assignment2 (should be deleted)
        payload = {
            'legs': [
                {
                    'id': self.leg.id,
                    'shipment_assignments': [
                        {'id': assignment1.id, 'carrier': self.carrier.id, 'driver': self.driver3.id},
                        {'carrier': self.carrier.id, 'driver': self.driver2.id},
                    ]
                }
            ]
        }

        response = self.client.patch(self.load_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.leg.refresh_from_db()
        assignments = list(self.leg.shipment_assignments.all().order_by('id'))

        # Should have 2 assignments
        self.assertEqual(len(assignments), 2)

        # assignment1 should be updated to driver3
        assignment1.refresh_from_db()
        self.assertEqual(assignment1.driver_id, self.driver3.id)

        # assignment2 should be deleted
        self.assertFalse(ShipmentAssignment.objects.filter(id=assignment2.id).exists())

    def test_validation_driver_must_belong_to_carrier(self):
        """
        Test that driver must belong to the specified carrier.

        Should return validation error if driver doesn't belong to carrier.
        """
        payload = {
            'legs': [
                {
                    'shipment_assignments': [
                        {'carrier': self.carrier.id, 'driver': self.other_driver.id},
                    ]
                }
            ]
        }

        response = self.client.patch(self.load_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('driver', str(response.data).lower())

    def test_response_contains_shipment_assignments(self):
        """
        Test that response includes shipment_assignments in legs.
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
        self.assertIn('shipment_assignments', leg_data)
        self.assertEqual(len(leg_data['shipment_assignments']), 1)
        self.assertEqual(
            leg_data['shipment_assignments'][0]['carrier'],
            self.carrier.id
        )
        self.assertEqual(
            leg_data['shipment_assignments'][0]['driver'],
            self.driver1.id
        )
