"""
Test suite for the Agent functionality.

This module contains tests for:
1. SwapToolkit functionality
2. LoadToolkit functionality (including create_load)
3. New toolkit tests (AddressToolkit, CustomerToolkit, CarrierDriverToolkit, StopHistoryToolkit)
4. Agent creation and configuration
5. Team composition tests
6. Agent integration tests (requires OPENAI_API_KEY)
"""
import json
import os
from datetime import datetime, timedelta
from unittest import skipUnless
from zoneinfo import ZoneInfo

from agno.run.base import RunContext
from django.test import TestCase, override_settings
from django.utils import timezone

from machtms.agents.members import (
    dispatcher,
    planner,
    lead_team,
    load_parser,
    stop_builder,
    load_data_agent,
    carrier_assignment_agent,
    load_creation_team,
    lookup_agent,
)
from machtms.agents.toolkit import (
    LoadToolkit,
    SwapToolkit,
    AddressToolkit,
    CustomerToolkit,
    CarrierDriverToolkit,
    StopHistoryToolkit,
)
from machtms.backend.auth.models import Organization
from machtms.backend.legs.models import ShipmentAssignment
from machtms.backend.loads.models import Load, LoadStatus, BillingStatus
from machtms.backend.addresses.models import AddressUsageAccumulate
from machtms.core.factories import (
    AddressFactory,
    CarrierFactory,
    CustomerFactory,
    DriverFactory,
    LegFactory,
    LoadFactory,
    ShipmentAssignmentFactory,
    StopFactory,
)


def _make_run_context(organization):
    """Create a mock RunContext with the given organization in dependencies."""
    return RunContext(
        run_id="test-run",
        session_id="test-session",
        dependencies={"organization": organization},
    )


# ============================================================================
# SwapToolkit Tests
# ============================================================================

@override_settings(DEBUG=False)
class SwapToolkitTests(TestCase):
    """Tests for the SwapToolkit functionality."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com"
        )
        cls.carrier = CarrierFactory.create(organization=cls.organization)
        cls.driver_john = DriverFactory.create(
            carrier=cls.carrier,
            organization=cls.organization,
            first_name="John",
            last_name="Smith"
        )
        cls.driver_mike = DriverFactory.create(
            carrier=cls.carrier,
            organization=cls.organization,
            first_name="Mike",
            last_name="Johnson"
        )

    def setUp(self):
        self.load1 = LoadFactory.create(
            organization=self.organization,
            reference_number="LOAD-001"
        )
        self.load2 = LoadFactory.create(
            organization=self.organization,
            reference_number="LOAD-002"
        )
        self.leg1 = LegFactory.create(load=self.load1, organization=self.organization)
        self.leg2 = LegFactory.create(load=self.load2, organization=self.organization)

        self.assignment1 = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver_john,
            leg=self.leg1,
            organization=self.organization
        )
        self.assignment2 = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver_mike,
            leg=self.leg2,
            organization=self.organization
        )

        self.toolkit = SwapToolkit()
        self.ctx = _make_run_context(self.organization)

    def test_get_load_assignment_info_success(self):
        result = self.toolkit.get_load_assignment_info(self.ctx, "LOAD-001")
        self.assertIn("LOAD-001", result)
        self.assertIn("John Smith", result)
        self.assertIn(f"Leg {self.leg1.id}", result)

    def test_get_load_assignment_info_not_found(self):
        result = self.toolkit.get_load_assignment_info(self.ctx, "INVALID-REF")
        self.assertIn("not found", result.lower())

    def test_get_load_assignment_info_no_driver(self):
        load3 = LoadFactory.create(
            organization=self.organization,
            reference_number="LOAD-003"
        )
        LegFactory.create(load=load3, organization=self.organization)
        result = self.toolkit.get_load_assignment_info(self.ctx, "LOAD-003")
        self.assertIn("LOAD-003", result)
        self.assertIn("No driver assigned", result)

    def test_swap_drivers_between_loads_success(self):
        result = self.toolkit.swap_drivers_between_loads(self.ctx, "LOAD-001", "LOAD-002")
        self.assertIn("swap completed successfully", result.lower())
        self.assertIn("Mike Johnson", result)
        self.assertIn("John Smith", result)
        new_assignment1 = ShipmentAssignment.objects.get(leg=self.leg1)
        new_assignment2 = ShipmentAssignment.objects.get(leg=self.leg2)
        self.assertEqual(new_assignment1.driver_id, self.driver_mike.id)
        self.assertEqual(new_assignment2.driver_id, self.driver_john.id)

    def test_swap_with_invalid_first_reference(self):
        result = self.toolkit.swap_drivers_between_loads(self.ctx, "INVALID-REF", "LOAD-002")
        self.assertIn("INVALID-REF", result)
        self.assertIn("not found", result.lower())
        assignment1 = ShipmentAssignment.objects.get(leg=self.leg1)
        self.assertEqual(assignment1.driver_id, self.driver_john.id)

    def test_swap_with_invalid_second_reference(self):
        result = self.toolkit.swap_drivers_between_loads(self.ctx, "LOAD-001", "INVALID-REF")
        self.assertIn("INVALID-REF", result)
        self.assertIn("not found", result.lower())
        assignment1 = ShipmentAssignment.objects.get(leg=self.leg1)
        self.assertEqual(assignment1.driver_id, self.driver_john.id)

    def test_swap_with_no_driver_assigned_first_load(self):
        self.assignment1.delete()
        result = self.toolkit.swap_drivers_between_loads(self.ctx, "LOAD-001", "LOAD-002")
        self.assertIn("LOAD-001", result)
        self.assertIn("no driver assigned", result.lower())

    def test_swap_with_no_driver_assigned_second_load(self):
        self.assignment2.delete()
        result = self.toolkit.swap_drivers_between_loads(self.ctx, "LOAD-001", "LOAD-002")
        self.assertIn("LOAD-002", result)
        self.assertIn("no driver assigned", result.lower())


# ============================================================================
# LoadToolkit Tests — get_todays_loads
# ============================================================================

@override_settings(DEBUG=False)
class LoadToolkitTodaysLoadsTests(TestCase):
    """Tests for LoadToolkit.get_todays_loads functionality."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com"
        )
        cls.other_org = Organization.objects.create(
            company_name="Other Trucking Co",
            phone="555-999-9999",
            email="other@trucking.com"
        )
        cls.carrier = CarrierFactory.create(organization=cls.organization)
        cls.driver = DriverFactory.create(
            carrier=cls.carrier,
            organization=cls.organization,
            first_name="Alice",
            last_name="Trucker",
        )
        cls.customer = CustomerFactory.create(
            organization=cls.organization,
            customer_name="Acme Shipping",
        )

    def setUp(self):
        self.toolkit = LoadToolkit()
        self.ctx = _make_run_context(self.organization)
        self.pt = ZoneInfo("America/Los_Angeles")
        now_pt = datetime.now(self.pt)
        self.today_morning = now_pt.replace(hour=8, minute=0, second=0, microsecond=0)
        self.tomorrow_morning = self.today_morning + timedelta(days=1)

    def _create_load_with_pickup_today(self, ref, action='LL'):
        load = LoadFactory.create(
            organization=self.organization,
            reference_number=ref,
            customer=self.customer,
        )
        leg = LegFactory.create(load=load, organization=self.organization)
        ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver,
            leg=leg,
            organization=self.organization,
        )
        address = AddressFactory.create(
            organization=self.organization,
            street="123 Main St",
            city="Los Angeles",
            state="CA",
            zip_code="90001",
        )
        StopFactory.create(
            leg=leg,
            stop_number=1,
            action=action,
            address=address,
            start_range=self.today_morning,
            end_range=self.today_morning + timedelta(hours=2),
            organization=self.organization,
        )
        return load

    def test_returns_todays_loads(self):
        self._create_load_with_pickup_today("TODAY-001")
        result = self.toolkit.get_todays_loads(self.ctx)
        self.assertIn("TODAY-001", result)
        self.assertIn("Acme Shipping", result)

    def test_excludes_non_today_loads(self):
        load = LoadFactory.create(
            organization=self.organization,
            reference_number="TOMORROW-001",
        )
        leg = LegFactory.create(load=load, organization=self.organization)
        address = AddressFactory.create(organization=self.organization)
        StopFactory.create(
            leg=leg, stop_number=1, action='LL', address=address,
            start_range=self.tomorrow_morning,
            end_range=self.tomorrow_morning + timedelta(hours=2),
            organization=self.organization,
        )
        result = self.toolkit.get_todays_loads(self.ctx)
        self.assertNotIn("TOMORROW-001", result)

    def test_excludes_non_pickup_actions(self):
        load = LoadFactory.create(
            organization=self.organization,
            reference_number="DELIVERY-001",
        )
        leg = LegFactory.create(load=load, organization=self.organization)
        address = AddressFactory.create(organization=self.organization)
        StopFactory.create(
            leg=leg, stop_number=1, action='LU', address=address,
            start_range=self.today_morning,
            end_range=self.today_morning + timedelta(hours=2),
            organization=self.organization,
        )
        result = self.toolkit.get_todays_loads(self.ctx)
        self.assertNotIn("DELIVERY-001", result)

    def test_shows_driver_and_carrier_info(self):
        self._create_load_with_pickup_today("DETAILS-001")
        result = self.toolkit.get_todays_loads(self.ctx)
        self.assertIn("Alice Trucker", result)
        self.assertIn(self.carrier.carrier_name, result)

    def test_shows_address_info(self):
        self._create_load_with_pickup_today("ADDR-001")
        result = self.toolkit.get_todays_loads(self.ctx)
        self.assertIn("123 Main St", result)
        self.assertIn("Los Angeles", result)

    def test_handles_no_loads(self):
        result = self.toolkit.get_todays_loads(self.ctx)
        self.assertIn("No loads scheduled for pickup today", result)

    def test_respects_org_filtering(self):
        self._create_load_with_pickup_today("MYORG-001")
        other_load = LoadFactory.create(
            organization=self.other_org,
            reference_number="OTHERORG-001",
        )
        other_leg = LegFactory.create(load=other_load, organization=self.other_org)
        other_address = AddressFactory.create(organization=self.other_org)
        StopFactory.create(
            leg=other_leg, stop_number=1, action='LL', address=other_address,
            start_range=self.today_morning,
            end_range=self.today_morning + timedelta(hours=2),
            organization=self.other_org,
        )
        result = self.toolkit.get_todays_loads(self.ctx)
        self.assertIn("MYORG-001", result)
        self.assertNotIn("OTHERORG-001", result)

    def test_includes_all_pickup_action_types(self):
        for action in ['LL', 'HL', 'EMPP', 'HUBP']:
            self._create_load_with_pickup_today(f"ACTION-{action}", action=action)
        result = self.toolkit.get_todays_loads(self.ctx)
        for action in ['LL', 'HL', 'EMPP', 'HUBP']:
            self.assertIn(f"ACTION-{action}", result)


# ============================================================================
# LoadToolkit Tests — search_loads
# ============================================================================

@override_settings(DEBUG=False)
class LoadToolkitSearchTests(TestCase):
    """Tests for LoadToolkit.search_loads functionality."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com"
        )
        cls.other_org = Organization.objects.create(
            company_name="Other Trucking Co",
            phone="555-999-9999",
            email="other@trucking.com"
        )
        cls.carrier_alpha = CarrierFactory.create(
            organization=cls.organization,
            carrier_name="Alpha Transport",
        )
        cls.carrier_beta = CarrierFactory.create(
            organization=cls.organization,
            carrier_name="Beta Logistics",
        )
        cls.driver_alice = DriverFactory.create(
            carrier=cls.carrier_alpha,
            organization=cls.organization,
            first_name="Alice",
            last_name="Walker",
        )
        cls.driver_bob = DriverFactory.create(
            carrier=cls.carrier_beta,
            organization=cls.organization,
            first_name="Bob",
            last_name="Martinez",
        )
        cls.customer_acme = CustomerFactory.create(
            organization=cls.organization,
            customer_name="Acme Corp",
        )
        cls.customer_globex = CustomerFactory.create(
            organization=cls.organization,
            customer_name="Globex Inc",
        )

    def setUp(self):
        self.toolkit = LoadToolkit()
        self.ctx = _make_run_context(self.organization)
        now = timezone.now()

        self.load1 = LoadFactory.create(
            organization=self.organization,
            reference_number="SEARCH-001",
            customer=self.customer_acme,
            status=LoadStatus.DISPATCHED,
            billing_status=BillingStatus.PENDING_DELIVERY,
        )
        leg1 = LegFactory.create(load=self.load1, organization=self.organization)
        ShipmentAssignmentFactory.create(
            carrier=self.carrier_alpha, driver=self.driver_alice,
            leg=leg1, organization=self.organization,
        )
        addr1 = AddressFactory.create(
            organization=self.organization,
            street="456 Oak Street", city="Portland", state="OR", zip_code="97201",
        )
        StopFactory.create(
            leg=leg1, stop_number=1, action='LL', address=addr1,
            start_range=now, end_range=now + timedelta(hours=2),
            organization=self.organization,
        )

        self.load2 = LoadFactory.create(
            organization=self.organization,
            reference_number="SEARCH-002",
            customer=self.customer_globex,
            status=LoadStatus.PENDING,
            billing_status=BillingStatus.PAPERWORK_PENDING,
        )
        leg2 = LegFactory.create(load=self.load2, organization=self.organization)
        ShipmentAssignmentFactory.create(
            carrier=self.carrier_beta, driver=self.driver_bob,
            leg=leg2, organization=self.organization,
        )
        addr2 = AddressFactory.create(
            organization=self.organization,
            street="789 Elm Avenue", city="Seattle", state="WA", zip_code="98101",
        )
        StopFactory.create(
            leg=leg2, stop_number=1, action='LL', address=addr2,
            start_range=now, end_range=now + timedelta(hours=2),
            organization=self.organization,
        )

    def test_search_by_customer_name(self):
        result = self.toolkit.search_loads(self.ctx, customer_name="Acme")
        self.assertIn("SEARCH-001", result)
        self.assertNotIn("SEARCH-002", result)

    def test_search_by_carrier_name(self):
        result = self.toolkit.search_loads(self.ctx, carrier_name="Beta")
        self.assertIn("SEARCH-002", result)
        self.assertNotIn("SEARCH-001", result)

    def test_search_by_driver_name(self):
        result = self.toolkit.search_loads(self.ctx, driver_name="Alice")
        self.assertIn("SEARCH-001", result)
        self.assertNotIn("SEARCH-002", result)

    def test_search_by_driver_last_name(self):
        result = self.toolkit.search_loads(self.ctx, driver_name="Martinez")
        self.assertIn("SEARCH-002", result)
        self.assertNotIn("SEARCH-001", result)

    def test_search_by_street_address(self):
        result = self.toolkit.search_loads(self.ctx, street_address="Oak Street")
        self.assertIn("SEARCH-001", result)
        self.assertNotIn("SEARCH-002", result)

    def test_search_by_status(self):
        result = self.toolkit.search_loads(self.ctx, status="dispatched")
        self.assertIn("SEARCH-001", result)
        self.assertNotIn("SEARCH-002", result)

    def test_search_by_billing_status(self):
        result = self.toolkit.search_loads(self.ctx, billing_status="paperwork_pending")
        self.assertIn("SEARCH-002", result)
        self.assertNotIn("SEARCH-001", result)

    def test_combined_and_search(self):
        result = self.toolkit.search_loads(self.ctx, customer_name="Acme", status="dispatched")
        self.assertIn("SEARCH-001", result)
        self.assertNotIn("SEARCH-002", result)

    def test_combined_search_no_match(self):
        result = self.toolkit.search_loads(self.ctx, customer_name="Acme", status="pending")
        self.assertIn("No loads found", result)

    def test_no_criteria_error(self):
        result = self.toolkit.search_loads(self.ctx)
        self.assertIn("Error", result)
        self.assertIn("At least one search criterion", result)

    def test_invalid_status_error(self):
        result = self.toolkit.search_loads(self.ctx, status="invalid_status")
        self.assertIn("Error", result)
        self.assertIn("Invalid status", result)

    def test_invalid_billing_status_error(self):
        result = self.toolkit.search_loads(self.ctx, billing_status="bad_billing")
        self.assertIn("Error", result)
        self.assertIn("Invalid billing_status", result)

    def test_no_results_message(self):
        result = self.toolkit.search_loads(self.ctx, customer_name="Nonexistent Corp")
        self.assertIn("No loads found", result)

    def test_case_insensitive_customer_search(self):
        result = self.toolkit.search_loads(self.ctx, customer_name="acme")
        self.assertIn("SEARCH-001", result)

    def test_case_insensitive_driver_search(self):
        result = self.toolkit.search_loads(self.ctx, driver_name="alice")
        self.assertIn("SEARCH-001", result)

    def test_org_filtering(self):
        other_customer = CustomerFactory.create(
            organization=self.other_org,
            customer_name="Acme International",
        )
        LoadFactory.create(
            organization=self.other_org,
            reference_number="OTHER-001",
            customer=other_customer,
        )
        result = self.toolkit.search_loads(self.ctx, customer_name="Acme")
        self.assertIn("SEARCH-001", result)
        self.assertNotIn("OTHER-001", result)


# ============================================================================
# LoadToolkit Tests — create_load
# ============================================================================

@override_settings(DEBUG=False)
class LoadToolkitCreateLoadTests(TestCase):
    """Tests for LoadToolkit.create_load functionality."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com"
        )
        cls.carrier = CarrierFactory.create(organization=cls.organization)
        cls.driver = DriverFactory.create(
            carrier=cls.carrier,
            organization=cls.organization,
            first_name="Alice",
            last_name="Trucker",
        )
        cls.customer = CustomerFactory.create(
            organization=cls.organization,
            customer_name="Acme Shipping",
        )
        cls.address1 = AddressFactory.create(
            organization=cls.organization,
            street="123 Main St", city="Los Angeles", state="CA", zip_code="90001",
        )
        cls.address2 = AddressFactory.create(
            organization=cls.organization,
            street="456 Oak St", city="Portland", state="OR", zip_code="97201",
        )

    def setUp(self):
        self.toolkit = LoadToolkit()
        self.ctx = _make_run_context(self.organization)

    def test_create_load_success(self):
        """Test creating a load with valid payload."""
        payload = {
            "customer": self.customer.pk,
            "reference_number": "NEW-001",
            "bol_number": "BOL-123",
            "trailer_type": "LARGE_53",
            "legs": [{
                "stops": [
                    {
                        "stop_number": 1,
                        "address": self.address1.pk,
                        "action": "LL",
                        "start_range": "2025-06-01T16:00:00Z",
                    },
                    {
                        "stop_number": 2,
                        "address": self.address2.pk,
                        "action": "LU",
                        "start_range": "2025-06-01T22:00:00Z",
                    },
                ],
                "shipment_assignment": {
                    "carrier": self.carrier.pk,
                    "driver": self.driver.pk,
                },
            }],
        }
        result = self.toolkit.create_load(self.ctx, json.dumps(payload))
        self.assertIn("Load created successfully", result)
        self.assertIn("NEW-001", result)

        load = Load.objects.get(reference_number="NEW-001")
        self.assertEqual(load.customer_id, self.customer.pk)
        self.assertEqual(load.trailer_type, "LARGE_53")
        self.assertEqual(load.legs.count(), 1)

        leg = load.legs.first()
        self.assertEqual(leg.stops.count(), 2)
        self.assertTrue(hasattr(leg, 'shipment_assignment'))
        self.assertEqual(leg.shipment_assignment.driver_id, self.driver.pk)

    def test_create_load_minimal(self):
        """Test creating a load with minimal payload (no legs)."""
        payload = {"reference_number": "MINIMAL-001"}
        result = self.toolkit.create_load(self.ctx, json.dumps(payload))
        self.assertIn("Load created successfully", result)
        load = Load.objects.get(reference_number="MINIMAL-001")
        self.assertEqual(load.status, "pending")
        self.assertEqual(load.billing_status, "pending_delivery")

    def test_create_load_invalid_json(self):
        """Test that invalid JSON returns an error."""
        result = self.toolkit.create_load(self.ctx, "not valid json{")
        self.assertIn("Error: Invalid JSON", result)

    def test_create_load_invalid_action_transition(self):
        """Test that invalid stop action transitions are caught."""
        payload = {
            "legs": [{
                "stops": [
                    {
                        "stop_number": 1,
                        "address": self.address1.pk,
                        "action": "LL",
                        "start_range": "2025-06-01T16:00:00Z",
                    },
                    {
                        "stop_number": 2,
                        "address": self.address2.pk,
                        "action": "LL",  # LL after LL is invalid
                        "start_range": "2025-06-01T22:00:00Z",
                    },
                ],
            }],
        }
        result = self.toolkit.create_load(self.ctx, json.dumps(payload))
        self.assertIn("Validation errors", result)

    def test_create_load_without_assignment(self):
        """Test creating a load with stops but no shipment assignment."""
        payload = {
            "reference_number": "NO-ASSIGN-001",
            "legs": [{
                "stops": [
                    {
                        "stop_number": 1,
                        "address": self.address1.pk,
                        "action": "LL",
                        "start_range": "2025-06-01T16:00:00Z",
                    },
                    {
                        "stop_number": 2,
                        "address": self.address2.pk,
                        "action": "LU",
                        "start_range": "2025-06-01T22:00:00Z",
                    },
                ],
            }],
        }
        result = self.toolkit.create_load(self.ctx, json.dumps(payload))
        self.assertIn("Load created successfully", result)
        load = Load.objects.get(reference_number="NO-ASSIGN-001")
        leg = load.legs.first()
        self.assertFalse(hasattr(leg, 'shipment_assignment') and leg.shipment_assignment is not None)


# ============================================================================
# AddressToolkit Tests
# ============================================================================

@override_settings(DEBUG=False)
class AddressToolkitTests(TestCase):
    """Tests for the AddressToolkit functionality."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com"
        )
        cls.other_org = Organization.objects.create(
            company_name="Other Trucking Co",
            phone="555-999-9999",
            email="other@trucking.com"
        )
        cls.address1 = AddressFactory.create(
            organization=cls.organization,
            street="123 Main Street",
            city="Los Angeles",
            state="CA",
            zip_code="90001",
        )
        cls.address2 = AddressFactory.create(
            organization=cls.organization,
            street="456 Oak Avenue",
            city="Portland",
            state="OR",
            zip_code="97201",
        )
        cls.other_org_address = AddressFactory.create(
            organization=cls.other_org,
            street="123 Main Street",
            city="Los Angeles",
            state="CA",
            zip_code="90001",
        )

    def setUp(self):
        self.toolkit = AddressToolkit()
        self.ctx = _make_run_context(self.organization)

    def test_search_by_street(self):
        result = self.toolkit.search_addresses(self.ctx, street="Main")
        self.assertIn("123 Main Street", result)
        self.assertNotIn("456 Oak", result)

    def test_search_by_city(self):
        result = self.toolkit.search_addresses(self.ctx, city="Portland")
        self.assertIn("456 Oak Avenue", result)
        self.assertNotIn("Main Street", result)

    def test_search_by_state(self):
        result = self.toolkit.search_addresses(self.ctx, state="CA")
        self.assertIn("123 Main Street", result)

    def test_search_by_zip(self):
        result = self.toolkit.search_addresses(self.ctx, zip_code="97201")
        self.assertIn("456 Oak Avenue", result)

    def test_search_no_criteria_error(self):
        result = self.toolkit.search_addresses(self.ctx)
        self.assertIn("Error", result)

    def test_search_no_results(self):
        result = self.toolkit.search_addresses(self.ctx, street="Nonexistent")
        self.assertIn("No addresses found", result)

    def test_search_respects_org(self):
        result = self.toolkit.search_addresses(self.ctx, street="Main")
        self.assertIn(f"ID {self.address1.pk}", result)
        self.assertNotIn(f"ID {self.other_org_address.pk}", result)

    def test_ensure_address_creates_new(self):
        result = self.toolkit.ensure_address(
            self.ctx, street="999 New St", city="Denver", state="CO", zip_code="80201"
        )
        self.assertIn("Created new", result)
        self.assertIn("999 New St", result)

    def test_ensure_address_finds_existing(self):
        result = self.toolkit.ensure_address(
            self.ctx, street="123 Main Street", city="Los Angeles", state="CA", zip_code="90001"
        )
        self.assertIn("Found existing", result)
        self.assertIn(f"ID {self.address1.pk}", result)

    def test_get_recent_addresses_for_customer(self):
        from machtms.backend.addresses.models import AddressUsageByCustomerAccumulate
        customer = CustomerFactory.create(organization=self.organization)
        AddressUsageByCustomerAccumulate.objects.create(
            organization=self.organization,
            address=self.address1,
            customer=customer,
            last_used=timezone.now(),
        )
        result = self.toolkit.get_recent_addresses_for_customer(self.ctx, customer_id=customer.pk)
        self.assertIn("123 Main Street", result)

    def test_get_recent_addresses_none(self):
        customer = CustomerFactory.create(organization=self.organization)
        result = self.toolkit.get_recent_addresses_for_customer(self.ctx, customer_id=customer.pk)
        self.assertIn("No recent addresses", result)

    def test_list_addresses(self):
        result = self.toolkit.list_addresses(self.ctx)
        self.assertIn("123 Main Street", result)
        self.assertIn("456 Oak Avenue", result)
        self.assertIn(f"ID {self.address1.pk}", result)
        self.assertIn(f"ID {self.address2.pk}", result)

    def test_list_addresses_empty(self):
        other_ctx = _make_run_context(self.other_org)
        # other_org has one address from setUpTestData
        # Create a fresh org with no addresses
        empty_org = Organization.objects.create(
            company_name="Empty Org", phone="555-000-0000", email="empty@org.com"
        )
        empty_ctx = _make_run_context(empty_org)
        result = self.toolkit.list_addresses(empty_ctx)
        self.assertIn("No addresses found", result)

    def test_list_addresses_respects_org(self):
        result = self.toolkit.list_addresses(self.ctx)
        self.assertNotIn(f"ID {self.other_org_address.pk}", result)

    def test_get_recently_used_addresses(self):
        AddressUsageAccumulate.objects.create(
            organization=self.organization,
            address=self.address1,
            last_used=timezone.now(),
        )
        result = self.toolkit.get_recently_used_addresses(self.ctx)
        self.assertIn("123 Main Street", result)
        self.assertIn("last used:", result)

    def test_get_recently_used_addresses_none(self):
        result = self.toolkit.get_recently_used_addresses(self.ctx)
        self.assertIn("No addresses used", result)

    def test_get_recently_used_addresses_excludes_old(self):
        AddressUsageAccumulate.objects.create(
            organization=self.organization,
            address=self.address1,
            last_used=timezone.now() - timedelta(days=60),
        )
        result = self.toolkit.get_recently_used_addresses(self.ctx, days_back=30)
        self.assertIn("No addresses used", result)


# ============================================================================
# CustomerToolkit Tests
# ============================================================================

@override_settings(DEBUG=False)
class CustomerToolkitTests(TestCase):
    """Tests for the CustomerToolkit functionality."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com"
        )
        cls.other_org = Organization.objects.create(
            company_name="Other Trucking Co",
            phone="555-999-9999",
            email="other@trucking.com"
        )
        cls.customer_acme = CustomerFactory.create(
            organization=cls.organization,
            customer_name="Acme Corp",
            phone_number="555-111-1111",
        )
        cls.customer_globex = CustomerFactory.create(
            organization=cls.organization,
            customer_name="Globex Inc",
        )
        cls.other_org_customer = CustomerFactory.create(
            organization=cls.other_org,
            customer_name="Acme International",
        )

    def setUp(self):
        self.toolkit = CustomerToolkit()
        self.ctx = _make_run_context(self.organization)

    def test_search_by_name(self):
        result = self.toolkit.search_customers(self.ctx, name="Acme")
        self.assertIn("Acme Corp", result)
        self.assertNotIn("Globex", result)

    def test_search_case_insensitive(self):
        result = self.toolkit.search_customers(self.ctx, name="acme")
        self.assertIn("Acme Corp", result)

    def test_search_no_results(self):
        result = self.toolkit.search_customers(self.ctx, name="Nonexistent")
        self.assertIn("No customers found", result)

    def test_search_empty_name_error(self):
        result = self.toolkit.search_customers(self.ctx, name="")
        self.assertIn("Error", result)

    def test_search_respects_org(self):
        result = self.toolkit.search_customers(self.ctx, name="Acme")
        self.assertIn(f"ID {self.customer_acme.pk}", result)
        self.assertNotIn(f"ID {self.other_org_customer.pk}", result)

    def test_search_shows_phone(self):
        result = self.toolkit.search_customers(self.ctx, name="Acme")
        self.assertIn("555-111-1111", result)

    def test_list_customers(self):
        result = self.toolkit.list_customers(self.ctx)
        self.assertIn("Acme Corp", result)
        self.assertIn("Globex Inc", result)

    def test_list_customers_empty(self):
        empty_org = Organization.objects.create(
            company_name="Empty Org", phone="555-000-0000", email="empty@org.com"
        )
        empty_ctx = _make_run_context(empty_org)
        result = self.toolkit.list_customers(empty_ctx)
        self.assertIn("No customers found", result)

    def test_list_customers_respects_org(self):
        result = self.toolkit.list_customers(self.ctx)
        self.assertNotIn("Acme International", result)

    def test_list_customers_ordered_by_name(self):
        result = self.toolkit.list_customers(self.ctx)
        acme_pos = result.index("Acme Corp")
        globex_pos = result.index("Globex Inc")
        self.assertLess(acme_pos, globex_pos)

    def test_get_recently_active_customers(self):
        LoadFactory.create(
            organization=self.organization,
            customer=self.customer_acme,
            reference_number="RECENT-CUST-001",
        )
        result = self.toolkit.get_recently_active_customers(self.ctx)
        self.assertIn("Acme Corp", result)
        self.assertIn("Recent loads:", result)

    def test_get_recently_active_customers_none(self):
        result = self.toolkit.get_recently_active_customers(self.ctx)
        self.assertIn("No customers with loads", result)

    def test_get_recently_active_customers_respects_org(self):
        LoadFactory.create(
            organization=self.organization,
            customer=self.customer_acme,
            reference_number="MY-ORG-LOAD",
        )
        result = self.toolkit.get_recently_active_customers(self.ctx)
        self.assertIn("Acme Corp", result)
        self.assertNotIn("Acme International", result)


# ============================================================================
# CarrierDriverToolkit Tests
# ============================================================================

@override_settings(DEBUG=False)
class CarrierDriverToolkitTests(TestCase):
    """Tests for the CarrierDriverToolkit functionality."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com"
        )
        cls.other_org = Organization.objects.create(
            company_name="Other Trucking Co",
            phone="555-999-9999",
            email="other@trucking.com"
        )
        cls.carrier_alpha = CarrierFactory.create(
            organization=cls.organization,
            carrier_name="Alpha Transport",
        )
        cls.carrier_beta = CarrierFactory.create(
            organization=cls.organization,
            carrier_name="Beta Logistics",
        )
        cls.driver_alice = DriverFactory.create(
            carrier=cls.carrier_alpha,
            organization=cls.organization,
            first_name="Alice",
            last_name="Walker",
        )
        cls.driver_bob = DriverFactory.create(
            carrier=cls.carrier_beta,
            organization=cls.organization,
            first_name="Bob",
            last_name="Martinez",
        )

    def setUp(self):
        self.toolkit = CarrierDriverToolkit()
        self.ctx = _make_run_context(self.organization)

    def test_search_carriers_by_name(self):
        result = self.toolkit.search_carriers(self.ctx, carrier_name="Alpha")
        self.assertIn("Alpha Transport", result)
        self.assertNotIn("Beta", result)

    def test_search_carriers_case_insensitive(self):
        result = self.toolkit.search_carriers(self.ctx, carrier_name="alpha")
        self.assertIn("Alpha Transport", result)

    def test_search_carriers_no_results(self):
        result = self.toolkit.search_carriers(self.ctx, carrier_name="Nonexistent")
        self.assertIn("No carriers found", result)

    def test_search_carriers_empty_name_error(self):
        result = self.toolkit.search_carriers(self.ctx, carrier_name="")
        self.assertIn("Error", result)

    def test_search_drivers_by_first_name(self):
        result = self.toolkit.search_drivers(self.ctx, driver_name="Alice")
        self.assertIn("Alice Walker", result)
        self.assertNotIn("Bob", result)

    def test_search_drivers_by_last_name(self):
        result = self.toolkit.search_drivers(self.ctx, driver_name="Martinez")
        self.assertIn("Bob Martinez", result)
        self.assertNotIn("Alice", result)

    def test_search_drivers_shows_carrier(self):
        result = self.toolkit.search_drivers(self.ctx, driver_name="Alice")
        self.assertIn("Alpha Transport", result)

    def test_search_drivers_no_results(self):
        result = self.toolkit.search_drivers(self.ctx, driver_name="Nonexistent")
        self.assertIn("No drivers found", result)

    def test_search_drivers_empty_name_error(self):
        result = self.toolkit.search_drivers(self.ctx, driver_name="")
        self.assertIn("Error", result)

    def test_get_drivers_for_carrier(self):
        result = self.toolkit.get_drivers_for_carrier(self.ctx, carrier_id=self.carrier_alpha.pk)
        self.assertIn("Alice Walker", result)
        self.assertIn("Alpha Transport", result)

    def test_get_drivers_for_carrier_not_found(self):
        result = self.toolkit.get_drivers_for_carrier(self.ctx, carrier_id=99999)
        self.assertIn("not found", result.lower())

    def test_get_recent_driver_loads(self):
        load = LoadFactory.create(organization=self.organization, reference_number="RECENT-001")
        leg = LegFactory.create(load=load, organization=self.organization)
        ShipmentAssignmentFactory.create(
            carrier=self.carrier_alpha,
            driver=self.driver_alice,
            leg=leg,
            organization=self.organization,
        )
        result = self.toolkit.get_recent_driver_loads(self.ctx, driver_name="Alice")
        self.assertIn("Alice Walker", result)
        self.assertIn("RECENT-001", result)

    def test_get_recent_driver_loads_no_results(self):
        result = self.toolkit.get_recent_driver_loads(self.ctx, driver_name="Nonexistent")
        self.assertIn("No recent loads found", result)

    def test_get_recent_driver_loads_empty_name_error(self):
        result = self.toolkit.get_recent_driver_loads(self.ctx, driver_name="")
        self.assertIn("Error", result)

    def test_list_carriers(self):
        result = self.toolkit.list_carriers(self.ctx)
        self.assertIn("Alpha Transport", result)
        self.assertIn("Beta Logistics", result)

    def test_list_carriers_empty(self):
        empty_org = Organization.objects.create(
            company_name="Empty Org", phone="555-000-0000", email="empty@org.com"
        )
        empty_ctx = _make_run_context(empty_org)
        result = self.toolkit.list_carriers(empty_ctx)
        self.assertIn("No carriers found", result)

    def test_list_carriers_ordered_by_name(self):
        result = self.toolkit.list_carriers(self.ctx)
        alpha_pos = result.index("Alpha Transport")
        beta_pos = result.index("Beta Logistics")
        self.assertLess(alpha_pos, beta_pos)

    def test_list_carriers_shows_driver_count(self):
        result = self.toolkit.list_carriers(self.ctx)
        self.assertIn("Drivers:", result)

    def test_list_drivers(self):
        result = self.toolkit.list_drivers(self.ctx)
        self.assertIn("Bob Martinez", result)
        self.assertIn("Alice Walker", result)

    def test_list_drivers_empty(self):
        empty_org = Organization.objects.create(
            company_name="Empty Org", phone="555-000-0000", email="empty@org.com"
        )
        empty_ctx = _make_run_context(empty_org)
        result = self.toolkit.list_drivers(empty_ctx)
        self.assertIn("No drivers found", result)

    def test_list_drivers_ordered_by_last_name(self):
        result = self.toolkit.list_drivers(self.ctx)
        martinez_pos = result.index("Bob Martinez")
        walker_pos = result.index("Alice Walker")
        self.assertLess(martinez_pos, walker_pos)

    def test_list_drivers_shows_carrier(self):
        result = self.toolkit.list_drivers(self.ctx)
        self.assertIn("Alpha Transport", result)
        self.assertIn("Beta Logistics", result)

    def test_get_recently_active_carriers(self):
        load = LoadFactory.create(organization=self.organization, reference_number="ACTIVE-C-001")
        leg = LegFactory.create(load=load, organization=self.organization)
        ShipmentAssignmentFactory.create(
            carrier=self.carrier_alpha,
            driver=self.driver_alice,
            leg=leg,
            organization=self.organization,
        )
        result = self.toolkit.get_recently_active_carriers(self.ctx)
        self.assertIn("Alpha Transport", result)
        self.assertIn("Recent assignments:", result)

    def test_get_recently_active_carriers_none(self):
        result = self.toolkit.get_recently_active_carriers(self.ctx)
        self.assertIn("No carriers with assignments", result)

    def test_get_recently_active_drivers(self):
        load = LoadFactory.create(organization=self.organization, reference_number="ACTIVE-D-001")
        leg = LegFactory.create(load=load, organization=self.organization)
        ShipmentAssignmentFactory.create(
            carrier=self.carrier_alpha,
            driver=self.driver_alice,
            leg=leg,
            organization=self.organization,
        )
        result = self.toolkit.get_recently_active_drivers(self.ctx)
        self.assertIn("Alice Walker", result)
        self.assertIn("Alpha Transport", result)
        self.assertIn("Recent assignments:", result)

    def test_get_recently_active_drivers_none(self):
        result = self.toolkit.get_recently_active_drivers(self.ctx)
        self.assertIn("No drivers with assignments", result)


# ============================================================================
# StopHistoryToolkit Tests
# ============================================================================

@override_settings(DEBUG=False)
class StopHistoryToolkitTests(TestCase):
    """Tests for the StopHistoryToolkit functionality."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com"
        )
        cls.address = AddressFactory.create(
            organization=cls.organization,
            street="123 Main St",
            city="Los Angeles",
            state="CA",
            zip_code="90001",
        )

    def setUp(self):
        self.toolkit = StopHistoryToolkit()
        self.ctx = _make_run_context(self.organization)

    def test_get_similar_stops(self):
        load = LoadFactory.create(organization=self.organization)
        leg = LegFactory.create(load=load, organization=self.organization)
        StopFactory.create(
            leg=leg, stop_number=1, action='LL', address=self.address,
            start_range=timezone.now(), organization=self.organization,
        )
        result = self.toolkit.get_similar_stops_for_address(self.ctx, address_id=self.address.pk)
        self.assertIn("LIVE LOAD", result)
        self.assertIn("LL", result)

    def test_get_similar_stops_no_results(self):
        result = self.toolkit.get_similar_stops_for_address(self.ctx, address_id=99999)
        self.assertIn("No previous stops found", result)


# ============================================================================
# Agent Creation Tests
# ============================================================================

@override_settings(DEBUG=False)
class AgentCreationTests(TestCase):
    """Tests for agent creation and configuration."""

    def test_planner_agent_name(self):
        self.assertEqual(planner.name, "Swap Planner")

    def test_planner_agent_has_tools(self):
        self.assertIsNotNone(planner.tools)
        self.assertTrue(len(planner.tools) > 0)

    def test_planner_agent_has_swap_toolkit(self):
        toolkit_names = [tool.name for tool in planner.tools]
        self.assertIn("swap_toolkit", toolkit_names)

    def test_planner_agent_has_load_toolkit(self):
        toolkit_names = [tool.name for tool in planner.tools]
        self.assertIn("load_toolkit", toolkit_names)

    def test_dispatcher_agent_name(self):
        self.assertEqual(dispatcher.name, "Dispatcher")

    def test_dispatcher_agent_has_tools(self):
        self.assertIsNotNone(dispatcher.tools)
        self.assertTrue(len(dispatcher.tools) > 0)

    def test_dispatcher_agent_has_load_toolkit(self):
        toolkit_names = [tool.name for tool in dispatcher.tools]
        self.assertIn("load_toolkit", toolkit_names)

    def test_lookup_agent_name(self):
        self.assertEqual(lookup_agent.name, "Lookup Agent")

    def test_lookup_agent_has_tools(self):
        self.assertIsNotNone(lookup_agent.tools)
        self.assertTrue(len(lookup_agent.tools) > 0)

    def test_lookup_agent_has_address_toolkit(self):
        toolkit_names = [tool.name for tool in lookup_agent.tools]
        self.assertIn("address_toolkit", toolkit_names)

    def test_lookup_agent_has_customer_toolkit(self):
        toolkit_names = [tool.name for tool in lookup_agent.tools]
        self.assertIn("customer_toolkit", toolkit_names)

    def test_lookup_agent_has_carrier_driver_toolkit(self):
        toolkit_names = [tool.name for tool in lookup_agent.tools]
        self.assertIn("carrier_driver_toolkit", toolkit_names)


# ============================================================================
# Load Creation Agent Tests
# ============================================================================

@override_settings(DEBUG=False)
class LoadCreationAgentTests(TestCase):
    """Tests for load creation agent configuration."""

    def test_load_parser_name(self):
        self.assertEqual(load_parser.name, "Load Parser")

    def test_load_parser_has_no_tools(self):
        self.assertTrue(load_parser.tools is None or len(load_parser.tools) == 0)

    def test_stop_builder_name(self):
        self.assertEqual(stop_builder.name, "Stop Builder")

    def test_stop_builder_has_address_toolkit(self):
        toolkit_names = [tool.name for tool in stop_builder.tools]
        self.assertIn("address_toolkit", toolkit_names)

    def test_stop_builder_has_stop_history_toolkit(self):
        toolkit_names = [tool.name for tool in stop_builder.tools]
        self.assertIn("stop_history_toolkit", toolkit_names)

    def test_load_data_agent_name(self):
        self.assertEqual(load_data_agent.name, "Load Data Agent")

    def test_load_data_agent_has_customer_toolkit(self):
        toolkit_names = [tool.name for tool in load_data_agent.tools]
        self.assertIn("customer_toolkit", toolkit_names)

    def test_carrier_assignment_agent_name(self):
        self.assertEqual(carrier_assignment_agent.name, "Carrier Assignment Agent")

    def test_carrier_assignment_agent_has_carrier_driver_toolkit(self):
        toolkit_names = [tool.name for tool in carrier_assignment_agent.tools]
        self.assertIn("carrier_driver_toolkit", toolkit_names)


# ============================================================================
# Team Composition Tests
# ============================================================================

@override_settings(DEBUG=False)
class TeamCompositionTests(TestCase):
    """Tests for team composition and membership."""

    def test_load_creation_team_name(self):
        self.assertEqual(load_creation_team.name, "Load Creation Team")

    def test_load_creation_team_has_four_members(self):
        self.assertEqual(len(load_creation_team.members), 4)

    def test_load_creation_team_members(self):
        member_names = [m.name for m in load_creation_team.members]
        self.assertIn("Load Parser", member_names)
        self.assertIn("Stop Builder", member_names)
        self.assertIn("Load Data Agent", member_names)
        self.assertIn("Carrier Assignment Agent", member_names)

    def test_load_creation_team_has_load_toolkit(self):
        toolkit_names = [tool.name for tool in load_creation_team.tools]
        self.assertIn("load_toolkit", toolkit_names)

    def test_lead_team_name(self):
        self.assertEqual(lead_team.name, "TMS Lead Agent")

    def test_lead_team_has_four_members(self):
        self.assertEqual(len(lead_team.members), 4)

    def test_lead_team_includes_dispatcher(self):
        member_names = [m.name for m in lead_team.members]
        self.assertIn("Dispatcher", member_names)

    def test_lead_team_includes_planner(self):
        member_names = [m.name for m in lead_team.members]
        self.assertIn("Swap Planner", member_names)

    def test_lead_team_includes_load_creation_team(self):
        member_names = [m.name for m in lead_team.members]
        self.assertIn("Load Creation Team", member_names)

    def test_lead_team_includes_lookup_agent(self):
        member_names = [m.name for m in lead_team.members]
        self.assertIn("Lookup Agent", member_names)


# ============================================================================
# Integration Tests (requires OPENAI_API_KEY)
# ============================================================================

@skipUnless(os.environ.get('OPENAI_API_KEY'), "OPENAI_API_KEY not set")
@override_settings(DEBUG=False)
class SwapAgentIntegrationTests(TestCase):
    """
    Integration tests that actually run the agents with LLM calls.

    These tests require OPENAI_API_KEY to be set in the environment.
    They verify that the agent can understand swap requests and execute them.
    """

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com"
        )
        cls.carrier = CarrierFactory.create(organization=cls.organization)
        cls.driver_john = DriverFactory.create(
            carrier=cls.carrier,
            organization=cls.organization,
            first_name="John",
            last_name="Smith"
        )
        cls.driver_mike = DriverFactory.create(
            carrier=cls.carrier,
            organization=cls.organization,
            first_name="Mike",
            last_name="Johnson"
        )

    def setUp(self):
        self.load1 = LoadFactory.create(
            organization=self.organization,
            reference_number="LOAD-001"
        )
        self.load2 = LoadFactory.create(
            organization=self.organization,
            reference_number="LOAD-002"
        )
        self.leg1 = LegFactory.create(load=self.load1, organization=self.organization)
        self.leg2 = LegFactory.create(load=self.load2, organization=self.organization)

        self.assignment1 = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver_john,
            leg=self.leg1,
            organization=self.organization
        )
        self.assignment2 = ShipmentAssignmentFactory.create(
            carrier=self.carrier,
            driver=self.driver_mike,
            leg=self.leg2,
            organization=self.organization
        )

    def test_planner_agent_swaps_drivers(self):
        response = planner.run(
            "Swap the drivers between load LOAD-001 and LOAD-002",
            dependencies={"organization": self.organization},
        )
        response_text = response.content.lower()
        self.assertTrue(
            "swap" in response_text or "completed" in response_text or "success" in response_text,
            f"Expected swap confirmation in response: {response.content}"
        )
        new_assignment1 = ShipmentAssignment.objects.get(leg=self.leg1)
        new_assignment2 = ShipmentAssignment.objects.get(leg=self.leg2)
        self.assertEqual(new_assignment1.driver_id, self.driver_mike.id)
        self.assertEqual(new_assignment2.driver_id, self.driver_john.id)

    def test_planner_agent_handles_invalid_reference(self):
        response = planner.run(
            "Swap drivers between LOAD-001 and INVALID-LOAD",
            dependencies={"organization": self.organization},
        )
        response_text = response.content.lower()
        self.assertTrue(
            "not found" in response_text or "invalid" in response_text or "error" in response_text,
            f"Expected error message in response: {response.content}"
        )
        assignment1 = ShipmentAssignment.objects.get(leg=self.leg1)
        self.assertEqual(assignment1.driver_id, self.driver_john.id)

    def test_lead_team_delegates_swap_to_planner(self):
        response = lead_team.run(
            "I need to swap drivers between LOAD-001 and LOAD-002",
            dependencies={"organization": self.organization},
        )
        response_text = response.content.lower()
        self.assertTrue(
            "swap" in response_text or "completed" in response_text or "driver" in response_text,
            f"Expected swap-related response: {response.content}"
        )
        new_assignment1 = ShipmentAssignment.objects.get(leg=self.leg1)
        new_assignment2 = ShipmentAssignment.objects.get(leg=self.leg2)
        self.assertEqual(new_assignment1.driver_id, self.driver_mike.id)
        self.assertEqual(new_assignment2.driver_id, self.driver_john.id)
