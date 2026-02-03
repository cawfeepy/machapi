"""
Test suite for the address usage accumulation feature.

This module contains comprehensive tests for:
1. update_address_usage Celery task - Testing address usage record creation
2. Stop model save() behavior - Testing DirtyFieldsMixin integration
3. Edge cases - Testing error handling and boundary conditions

The address usage accumulation feature tracks how often addresses are used
across the system, both globally and per-customer, enabling analytics and
recency-based address suggestions.
"""
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings

from machtms.backend.addresses.models import (
    Address,
    AddressUsageAccumulate,
    AddressUsageByCustomerAccumulate,
)
from machtms.core.factories.routes import StopFactory
from machtms.core.factories.addresses import AddressFactory
from machtms.core.factories.leg import LegFactory
from machtms.core.factories.loads import LoadFactory
from machtms.core.factories.customer import CustomerFactory
from machtms.core.tasks.addresses import update_address_usage


class UpdateAddressUsageTaskTests(TestCase):
    """
    Tests for the update_address_usage Celery task.

    These tests verify that the task correctly creates accumulation records
    for address usage tracking based on stop creation and updates.
    """

    def test_task_creates_general_usage_record(self):
        """
        Test that update_address_usage creates an AddressUsageAccumulate record.

        When the task is called with a valid stop_id and address_id, it should
        create a new record in AddressUsageAccumulate to track the usage.
        """
        # Create a load with a customer, leg, and stop
        customer = CustomerFactory()
        load = LoadFactory(customer=customer)
        leg = LegFactory(load=load)
        address = AddressFactory()

        # Create stop without triggering the task (we'll call it manually)
        with patch('machtms.backend.routes.models.Stop._dispatch_address_usage_task'):
            stop = StopFactory(leg=leg, address=address)

        initial_count = AddressUsageAccumulate.objects.count()

        # Call the task directly (synchronously for testing)
        update_address_usage(stop_id=stop.pk, address_id=address.pk)

        # Verify a new record was created
        self.assertEqual(
            AddressUsageAccumulate.objects.count(),
            initial_count + 1,
            "Should create one AddressUsageAccumulate record"
        )

        # Verify the record has the correct address
        new_record = AddressUsageAccumulate.objects.latest('id')
        self.assertEqual(
            new_record.address_id,
            address.pk,
            "Record should reference the correct address"
        )

    def test_task_creates_customer_usage_record_when_customer_exists(self):
        """
        Test that update_address_usage creates an AddressUsageByCustomerAccumulate
        record when the load has an associated customer.

        The customer-specific record enables tracking address usage per customer
        for personalized address suggestions.
        """
        # Create a load with a customer
        customer = CustomerFactory()
        load = LoadFactory(customer=customer)
        leg = LegFactory(load=load)
        address = AddressFactory()

        # Create stop without triggering the task
        with patch('machtms.backend.routes.models.Stop._dispatch_address_usage_task'):
            stop = StopFactory(leg=leg, address=address)

        initial_count = AddressUsageByCustomerAccumulate.objects.count()

        # Call the task directly
        update_address_usage(stop_id=stop.pk, address_id=address.pk)

        # Verify a customer-specific record was created
        self.assertEqual(
            AddressUsageByCustomerAccumulate.objects.count(),
            initial_count + 1,
            "Should create one AddressUsageByCustomerAccumulate record"
        )

        # Verify the record has correct references
        new_record = AddressUsageByCustomerAccumulate.objects.latest('id')
        self.assertEqual(new_record.address_id, address.pk)
        self.assertEqual(new_record.customer_id, customer.pk)

    def test_task_does_not_create_customer_record_when_no_customer(self):
        """
        Test that update_address_usage does NOT create an AddressUsageByCustomerAccumulate
        record when the load has no customer.

        This ensures we don't create invalid records with null customer references.
        """
        # Create a load WITHOUT a customer
        load = LoadFactory(customer=None)
        leg = LegFactory(load=load)
        address = AddressFactory()

        # Create stop without triggering the task
        with patch('machtms.backend.routes.models.Stop._dispatch_address_usage_task'):
            stop = StopFactory(leg=leg, address=address)

        initial_general_count = AddressUsageAccumulate.objects.count()
        initial_customer_count = AddressUsageByCustomerAccumulate.objects.count()

        # Call the task directly
        update_address_usage(stop_id=stop.pk, address_id=address.pk)

        # Verify general record was created
        self.assertEqual(
            AddressUsageAccumulate.objects.count(),
            initial_general_count + 1,
            "Should still create AddressUsageAccumulate record"
        )

        # Verify NO customer-specific record was created
        self.assertEqual(
            AddressUsageByCustomerAccumulate.objects.count(),
            initial_customer_count,
            "Should NOT create AddressUsageByCustomerAccumulate record when no customer"
        )

    def test_task_handles_nonexistent_stop_gracefully(self):
        """
        Test that update_address_usage handles a non-existent stop_id gracefully.

        The task should log a warning and return without creating any records
        when the stop doesn't exist.
        """
        address = AddressFactory()
        nonexistent_stop_id = 99999

        initial_general_count = AddressUsageAccumulate.objects.count()
        initial_customer_count = AddressUsageByCustomerAccumulate.objects.count()

        # Call the task with a non-existent stop_id
        # Should not raise an exception
        result = update_address_usage(stop_id=nonexistent_stop_id, address_id=address.pk)

        # Verify no records were created
        self.assertEqual(
            AddressUsageAccumulate.objects.count(),
            initial_general_count,
            "Should NOT create any records for non-existent stop"
        )
        self.assertEqual(
            AddressUsageByCustomerAccumulate.objects.count(),
            initial_customer_count,
            "Should NOT create any customer records for non-existent stop"
        )

        # Result should be None (early return)
        self.assertIsNone(result)


class StopModelSaveTests(TestCase):
    """
    Tests for the Stop model save() method and DirtyFieldsMixin integration.

    These tests verify that the Stop model correctly dispatches the
    update_address_usage task when:
    - A new stop is created
    - An existing stop's address is changed
    And does NOT dispatch when:
    - Other fields are updated without address change
    """

    @patch('machtms.backend.routes.models.Stop._dispatch_address_usage_task')
    def test_new_stop_dispatches_task(self, mock_dispatch):
        """
        Test that creating a new stop dispatches the address usage task.

        When a new Stop instance is created and saved, the save() method
        should call _dispatch_address_usage_task.
        """
        customer = CustomerFactory()
        load = LoadFactory(customer=customer)
        leg = LegFactory(load=load)
        address = AddressFactory()

        # Create a new stop
        stop = StopFactory(leg=leg, address=address)

        # Verify the dispatch method was called
        mock_dispatch.assert_called_once()

    @patch('machtms.backend.routes.models.Stop._dispatch_address_usage_task')
    def test_update_without_address_change_does_not_dispatch(self, mock_dispatch):
        """
        Test that updating a stop WITHOUT changing the address does NOT dispatch.

        When only non-address fields are modified (e.g., driver_notes), the
        task should NOT be dispatched since the address usage hasn't changed.
        """
        customer = CustomerFactory()
        load = LoadFactory(customer=customer)
        leg = LegFactory(load=load)
        address = AddressFactory()

        # Create initial stop (this will call dispatch once)
        stop = StopFactory(leg=leg, address=address)
        mock_dispatch.reset_mock()

        # Refresh from DB to reset dirty fields state
        stop.refresh_from_db()

        # Update only driver_notes (not the address)
        stop.driver_notes = "Updated notes - no address change"
        stop.save()

        # Verify dispatch was NOT called again
        mock_dispatch.assert_not_called()

    @patch('machtms.backend.routes.models.Stop._dispatch_address_usage_task')
    def test_update_with_address_change_dispatches_task(self, mock_dispatch):
        """
        Test that updating a stop WITH an address change DOES dispatch the task.

        When the address field is modified, the task should be dispatched
        to track usage of the new address.
        """
        customer = CustomerFactory()
        load = LoadFactory(customer=customer)
        leg = LegFactory(load=load)
        address1 = AddressFactory()
        address2 = AddressFactory()

        # Create initial stop with address1
        stop = StopFactory(leg=leg, address=address1)
        mock_dispatch.reset_mock()

        # Refresh from DB to reset dirty fields state
        stop.refresh_from_db()

        # Change the address to address2
        stop.address = address2
        stop.save()

        # Verify dispatch WAS called for the address change
        mock_dispatch.assert_called_once()

    @patch('machtms.backend.routes.models.Stop._dispatch_address_usage_task')
    def test_update_multiple_fields_with_address_dispatches_once(self, mock_dispatch):
        """
        Test that updating multiple fields including address dispatches once.

        When multiple fields are updated along with the address, the task
        should only be dispatched once.
        """
        customer = CustomerFactory()
        load = LoadFactory(customer=customer)
        leg = LegFactory(load=load)
        address1 = AddressFactory()
        address2 = AddressFactory()

        # Create initial stop
        stop = StopFactory(leg=leg, address=address1)
        mock_dispatch.reset_mock()

        # Refresh from DB to reset dirty fields state
        stop.refresh_from_db()

        # Update multiple fields including address
        stop.address = address2
        stop.driver_notes = "Updated notes"
        stop.po_numbers = "PO-UPDATED"
        stop.save()

        # Verify dispatch was called exactly once
        mock_dispatch.assert_called_once()

    @patch('machtms.backend.routes.models.Stop._dispatch_address_usage_task')
    def test_update_multiple_fields_without_address_does_not_dispatch(self, mock_dispatch):
        """
        Test that updating multiple non-address fields does NOT dispatch.

        When multiple fields are updated but address is unchanged, no task
        should be dispatched.
        """
        customer = CustomerFactory()
        load = LoadFactory(customer=customer)
        leg = LegFactory(load=load)
        address = AddressFactory()

        # Create initial stop
        stop = StopFactory(leg=leg, address=address)
        mock_dispatch.reset_mock()

        # Refresh from DB to reset dirty fields state
        stop.refresh_from_db()

        # Update multiple fields WITHOUT changing address
        stop.driver_notes = "Updated notes"
        stop.po_numbers = "PO-UPDATED"
        stop.action = 'LU'
        stop.save()

        # Verify dispatch was NOT called
        mock_dispatch.assert_not_called()


class AddressUsageIntegrationTests(TestCase):
    """
    Integration tests for the complete address usage accumulation flow.

    These tests verify the end-to-end behavior from stop creation/update
    through to the actual database record creation, with mocked Celery
    task dispatch to allow synchronous testing.
    """

    def test_new_stop_creates_usage_records_end_to_end(self):
        """
        Test the complete flow: new stop -> task dispatch -> record creation.

        This test mocks the CeleryController.delay method to intercept the
        task dispatch, then executes the task synchronously to verify the
        full integration.
        """
        customer = CustomerFactory()
        load = LoadFactory(customer=customer)
        leg = LegFactory(load=load)
        address = AddressFactory()

        initial_general_count = AddressUsageAccumulate.objects.count()
        initial_customer_count = AddressUsageByCustomerAccumulate.objects.count()

        # Mock the CeleryController instance's delay method to execute the task synchronously
        with patch.object(
            __import__('machtms.core.celerycontroller', fromlist=['controller']).controller,
            'delay',
            side_effect=lambda task, **kwargs: task(**kwargs)
        ) as mock_delay:
            # Create the stop - this should trigger the full flow
            stop = StopFactory(leg=leg, address=address)

            # Verify controller.delay was called with correct arguments
            mock_delay.assert_called_once()
            call_args = mock_delay.call_args
            self.assertEqual(call_args.kwargs['stop_id'], stop.pk)
            self.assertEqual(call_args.kwargs['address_id'], address.pk)

        # Verify both records were created
        self.assertEqual(
            AddressUsageAccumulate.objects.count(),
            initial_general_count + 1,
            "Should create AddressUsageAccumulate record"
        )
        self.assertEqual(
            AddressUsageByCustomerAccumulate.objects.count(),
            initial_customer_count + 1,
            "Should create AddressUsageByCustomerAccumulate record"
        )

    def test_address_change_creates_new_usage_records(self):
        """
        Test that changing a stop's address creates new usage records for the new address.

        When an address is changed, the system should track usage of the NEW address,
        not the old one.
        """
        customer = CustomerFactory()
        load = LoadFactory(customer=customer)
        leg = LegFactory(load=load)
        address1 = AddressFactory()
        address2 = AddressFactory()

        # Create initial stop without task dispatch
        with patch('machtms.backend.routes.models.Stop._dispatch_address_usage_task'):
            stop = StopFactory(leg=leg, address=address1)

        # Get initial counts (after first stop creation was suppressed)
        initial_general_count = AddressUsageAccumulate.objects.count()
        initial_customer_count = AddressUsageByCustomerAccumulate.objects.count()

        # Refresh from DB to reset dirty fields state
        stop.refresh_from_db()

        # Mock controller.delay for the address change
        with patch.object(
            __import__('machtms.core.celerycontroller', fromlist=['controller']).controller,
            'delay',
            side_effect=lambda task, **kwargs: task(**kwargs)
        ) as mock_delay:
            # Change the address
            stop.address = address2
            stop.save()

            # Verify the task was called with the NEW address
            mock_delay.assert_called_once()
            call_args = mock_delay.call_args
            self.assertEqual(call_args.kwargs['address_id'], address2.pk)

        # Verify records were created for the new address
        new_general_record = AddressUsageAccumulate.objects.latest('id')
        self.assertEqual(new_general_record.address_id, address2.pk)

        new_customer_record = AddressUsageByCustomerAccumulate.objects.latest('id')
        self.assertEqual(new_customer_record.address_id, address2.pk)

    def test_multiple_stops_create_multiple_records(self):
        """
        Test that creating multiple stops creates separate usage records for each.

        This verifies that the accumulation model correctly tracks each usage
        event independently.
        """
        customer = CustomerFactory()
        load = LoadFactory(customer=customer)
        leg = LegFactory(load=load)
        address = AddressFactory()

        initial_general_count = AddressUsageAccumulate.objects.count()

        # Mock controller.delay to execute synchronously
        with patch.object(
            __import__('machtms.core.celerycontroller', fromlist=['controller']).controller,
            'delay',
            side_effect=lambda task, **kwargs: task(**kwargs)
        ) as mock_delay:
            # Create multiple stops with the same address
            for i in range(3):
                StopFactory(leg=leg, address=address, stop_number=i+1)

        # Verify 3 records were created (one per stop)
        self.assertEqual(
            AddressUsageAccumulate.objects.count(),
            initial_general_count + 3,
            "Should create one record per stop"
        )

        # All records should reference the same address
        new_records = AddressUsageAccumulate.objects.order_by('-id')[:3]
        for record in new_records:
            self.assertEqual(record.address_id, address.pk)
