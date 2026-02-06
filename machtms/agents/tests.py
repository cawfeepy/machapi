"""
Test suite for the Agent functionality.

This module contains tests for:
1. SwapToolkit functionality
2. LoadToolkit functionality
3. Agent creation
4. Agent integration tests (requires OPENAI_API_KEY)
"""
import os
from datetime import datetime, timedelta
from unittest import skipUnless
from zoneinfo import ZoneInfo

from django.test import TestCase, override_settings
from django.utils import timezone

from machtms.agents.members import get_dispatcher_agent, get_lead_agent, get_planner_agent
from machtms.agents.toolkits import LoadToolkit, SwapToolkit
from machtms.backend.auth.models import Organization
from machtms.backend.legs.models import ShipmentAssignment
from machtms.backend.loads.models import LoadStatus, BillingStatus
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


@override_settings(DEBUG=False)
class SwapToolkitTests(TestCase):
    """Tests for the SwapToolkit functionality."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data that will be shared across all test methods."""
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
        """Set up test fixtures for each test method."""
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

        self.toolkit = SwapToolkit(organization=self.organization)

    def test_get_load_assignment_info_success(self):
        """Test retrieving load assignment info by reference number."""
        result = self.toolkit.get_load_assignment_info("LOAD-001")

        self.assertIn("LOAD-001", result)
        self.assertIn("John Smith", result)
        self.assertIn(f"Leg {self.leg1.id}", result)

    def test_get_load_assignment_info_not_found(self):
        """Test retrieving info for non-existent load."""
        result = self.toolkit.get_load_assignment_info("INVALID-REF")

        self.assertIn("not found", result.lower())

    def test_get_load_assignment_info_no_driver(self):
        """Test retrieving info for load without driver assignment."""
        load3 = LoadFactory.create(
            organization=self.organization,
            reference_number="LOAD-003"
        )
        LegFactory.create(load=load3, organization=self.organization)

        result = self.toolkit.get_load_assignment_info("LOAD-003")

        self.assertIn("LOAD-003", result)
        self.assertIn("No driver assigned", result)

    def test_swap_drivers_between_loads_success(self):
        """Test swapping drivers between two loads."""
        result = self.toolkit.swap_drivers_between_loads("LOAD-001", "LOAD-002")

        self.assertIn("swap completed successfully", result.lower())
        self.assertIn("Mike Johnson", result)
        self.assertIn("John Smith", result)

        new_assignment1 = ShipmentAssignment.objects.get(leg=self.leg1)
        new_assignment2 = ShipmentAssignment.objects.get(leg=self.leg2)

        self.assertEqual(new_assignment1.driver_id, self.driver_mike.id)
        self.assertEqual(new_assignment2.driver_id, self.driver_john.id)

    def test_swap_with_invalid_first_reference(self):
        """Test swap with invalid first reference number."""
        result = self.toolkit.swap_drivers_between_loads("INVALID-REF", "LOAD-002")

        self.assertIn("INVALID-REF", result)
        self.assertIn("not found", result.lower())

        assignment1 = ShipmentAssignment.objects.get(leg=self.leg1)
        self.assertEqual(assignment1.driver_id, self.driver_john.id)

    def test_swap_with_invalid_second_reference(self):
        """Test swap with invalid second reference number."""
        result = self.toolkit.swap_drivers_between_loads("LOAD-001", "INVALID-REF")

        self.assertIn("INVALID-REF", result)
        self.assertIn("not found", result.lower())

        assignment1 = ShipmentAssignment.objects.get(leg=self.leg1)
        self.assertEqual(assignment1.driver_id, self.driver_john.id)

    def test_swap_with_no_driver_assigned_first_load(self):
        """Test swap when first load has no driver assigned."""
        self.assignment1.delete()

        result = self.toolkit.swap_drivers_between_loads("LOAD-001", "LOAD-002")

        self.assertIn("LOAD-001", result)
        self.assertIn("no driver assigned", result.lower())

    def test_swap_with_no_driver_assigned_second_load(self):
        """Test swap when second load has no driver assigned."""
        self.assignment2.delete()

        result = self.toolkit.swap_drivers_between_loads("LOAD-001", "LOAD-002")

        self.assertIn("LOAD-002", result)
        self.assertIn("no driver assigned", result.lower())


@override_settings(DEBUG=False)
class AgentCreationTests(TestCase):
    """Tests for agent creation and configuration."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com"
        )

    def test_get_planner_agent_creates_agent(self):
        """Test that get_planner_agent creates an agent with correct configuration."""
        agent = get_planner_agent(self.organization)

        self.assertEqual(agent.name, "Swap Planner")
        self.assertIsNotNone(agent.tools)
        self.assertTrue(len(agent.tools) > 0)

    def test_get_lead_agent_creates_team(self):
        """Test that get_lead_agent creates a team with correct configuration."""
        team = get_lead_agent(self.organization)

        self.assertEqual(team.name, "TMS Lead Agent")
        self.assertIsNotNone(team.members)
        self.assertEqual(len(team.members), 2)

    def test_planner_agent_has_swap_toolkit(self):
        """Test that planner agent has SwapToolkit configured."""
        agent = get_planner_agent(self.organization)

        toolkit_names = [tool.name for tool in agent.tools]
        self.assertIn("swap_toolkit", toolkit_names)

    def test_lead_team_has_planner_member(self):
        """Test that lead team has planner agent as member."""
        team = get_lead_agent(self.organization)

        member_names = [member.name for member in team.members]
        self.assertIn("Swap Planner", member_names)

    def test_planner_agent_has_both_toolkits(self):
        """Test that planner agent has both SwapToolkit and LoadToolkit."""
        agent = get_planner_agent(self.organization)

        toolkit_names = [tool.name for tool in agent.tools]
        self.assertIn("swap_toolkit", toolkit_names)
        self.assertIn("load_toolkit", toolkit_names)


@override_settings(DEBUG=False)
class DispatcherAgentCreationTests(TestCase):
    """Tests for dispatcher agent creation and configuration."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com"
        )

    def test_get_dispatcher_agent_creates_agent(self):
        """Test that get_dispatcher_agent creates an agent with correct configuration."""
        agent = get_dispatcher_agent(self.organization)

        self.assertEqual(agent.name, "Dispatcher")
        self.assertIsNotNone(agent.tools)
        self.assertTrue(len(agent.tools) > 0)

    def test_dispatcher_agent_has_load_toolkit(self):
        """Test that dispatcher agent has LoadToolkit configured."""
        agent = get_dispatcher_agent(self.organization)

        toolkit_names = [tool.name for tool in agent.tools]
        self.assertIn("load_toolkit", toolkit_names)

    def test_lead_team_includes_dispatcher(self):
        """Test that lead team includes dispatcher as a member."""
        team = get_lead_agent(self.organization)

        member_names = [member.name for member in team.members]
        self.assertIn("Dispatcher", member_names)


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
        self.toolkit = LoadToolkit(organization=self.organization)
        self.pt = ZoneInfo("America/Los_Angeles")
        now_pt = datetime.now(self.pt)
        self.today_morning = now_pt.replace(hour=8, minute=0, second=0, microsecond=0)
        self.tomorrow_morning = self.today_morning + timedelta(days=1)

    def _create_load_with_pickup_today(self, ref, action='LL'):
        """Helper to create a load with a pickup stop today."""
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
        """Test that loads with pickup stops today are returned."""
        self._create_load_with_pickup_today("TODAY-001")

        result = self.toolkit.get_todays_loads()

        self.assertIn("TODAY-001", result)
        self.assertIn("Acme Shipping", result)

    def test_excludes_non_today_loads(self):
        """Test that loads with stops tomorrow are excluded."""
        load = LoadFactory.create(
            organization=self.organization,
            reference_number="TOMORROW-001",
        )
        leg = LegFactory.create(load=load, organization=self.organization)
        address = AddressFactory.create(organization=self.organization)
        StopFactory.create(
            leg=leg,
            stop_number=1,
            action='LL',
            address=address,
            start_range=self.tomorrow_morning,
            end_range=self.tomorrow_morning + timedelta(hours=2),
            organization=self.organization,
        )

        result = self.toolkit.get_todays_loads()

        self.assertNotIn("TOMORROW-001", result)

    def test_excludes_non_pickup_actions(self):
        """Test that loads with only delivery stops today are excluded."""
        load = LoadFactory.create(
            organization=self.organization,
            reference_number="DELIVERY-001",
        )
        leg = LegFactory.create(load=load, organization=self.organization)
        address = AddressFactory.create(organization=self.organization)
        StopFactory.create(
            leg=leg,
            stop_number=1,
            action='LU',
            address=address,
            start_range=self.today_morning,
            end_range=self.today_morning + timedelta(hours=2),
            organization=self.organization,
        )

        result = self.toolkit.get_todays_loads()

        self.assertNotIn("DELIVERY-001", result)

    def test_shows_driver_and_carrier_info(self):
        """Test that driver and carrier info is shown."""
        self._create_load_with_pickup_today("DETAILS-001")

        result = self.toolkit.get_todays_loads()

        self.assertIn("Alice Trucker", result)
        self.assertIn(self.carrier.carrier_name, result)

    def test_shows_address_info(self):
        """Test that stop address info is shown."""
        self._create_load_with_pickup_today("ADDR-001")

        result = self.toolkit.get_todays_loads()

        self.assertIn("123 Main St", result)
        self.assertIn("Los Angeles", result)

    def test_handles_no_loads(self):
        """Test that empty result is handled gracefully."""
        result = self.toolkit.get_todays_loads()

        self.assertIn("No loads scheduled for pickup today", result)

    def test_respects_org_filtering(self):
        """Test that only loads for the given organization are returned."""
        self._create_load_with_pickup_today("MYORG-001")

        # Create load in different org
        other_load = LoadFactory.create(
            organization=self.other_org,
            reference_number="OTHERORG-001",
        )
        other_leg = LegFactory.create(load=other_load, organization=self.other_org)
        other_address = AddressFactory.create(organization=self.other_org)
        StopFactory.create(
            leg=other_leg,
            stop_number=1,
            action='LL',
            address=other_address,
            start_range=self.today_morning,
            end_range=self.today_morning + timedelta(hours=2),
            organization=self.other_org,
        )

        result = self.toolkit.get_todays_loads()

        self.assertIn("MYORG-001", result)
        self.assertNotIn("OTHERORG-001", result)

    def test_includes_all_pickup_action_types(self):
        """Test that all pickup action types are included (LL, HL, EMPP, HUBP)."""
        for i, action in enumerate(['LL', 'HL', 'EMPP', 'HUBP'], start=1):
            self._create_load_with_pickup_today(f"ACTION-{action}", action=action)

        result = self.toolkit.get_todays_loads()

        for action in ['LL', 'HL', 'EMPP', 'HUBP']:
            self.assertIn(f"ACTION-{action}", result)


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
        self.toolkit = LoadToolkit(organization=self.organization)
        now = timezone.now()

        # Load 1: Acme + Alpha/Alice + "Oak Street"
        self.load1 = LoadFactory.create(
            organization=self.organization,
            reference_number="SEARCH-001",
            customer=self.customer_acme,
            status=LoadStatus.DISPATCHED,
            billing_status=BillingStatus.PENDING_DELIVERY,
        )
        leg1 = LegFactory.create(load=self.load1, organization=self.organization)
        ShipmentAssignmentFactory.create(
            carrier=self.carrier_alpha,
            driver=self.driver_alice,
            leg=leg1,
            organization=self.organization,
        )
        addr1 = AddressFactory.create(
            organization=self.organization,
            street="456 Oak Street",
            city="Portland",
            state="OR",
            zip_code="97201",
        )
        StopFactory.create(
            leg=leg1, stop_number=1, action='LL', address=addr1,
            start_range=now, end_range=now + timedelta(hours=2),
            organization=self.organization,
        )

        # Load 2: Globex + Beta/Bob + "Elm Avenue"
        self.load2 = LoadFactory.create(
            organization=self.organization,
            reference_number="SEARCH-002",
            customer=self.customer_globex,
            status=LoadStatus.PENDING,
            billing_status=BillingStatus.PAPERWORK_PENDING,
        )
        leg2 = LegFactory.create(load=self.load2, organization=self.organization)
        ShipmentAssignmentFactory.create(
            carrier=self.carrier_beta,
            driver=self.driver_bob,
            leg=leg2,
            organization=self.organization,
        )
        addr2 = AddressFactory.create(
            organization=self.organization,
            street="789 Elm Avenue",
            city="Seattle",
            state="WA",
            zip_code="98101",
        )
        StopFactory.create(
            leg=leg2, stop_number=1, action='LL', address=addr2,
            start_range=now, end_range=now + timedelta(hours=2),
            organization=self.organization,
        )

    def test_search_by_customer_name(self):
        """Test searching loads by customer name."""
        result = self.toolkit.search_loads(customer_name="Acme")

        self.assertIn("SEARCH-001", result)
        self.assertNotIn("SEARCH-002", result)

    def test_search_by_carrier_name(self):
        """Test searching loads by carrier name."""
        result = self.toolkit.search_loads(carrier_name="Beta")

        self.assertIn("SEARCH-002", result)
        self.assertNotIn("SEARCH-001", result)

    def test_search_by_driver_name(self):
        """Test searching loads by driver name."""
        result = self.toolkit.search_loads(driver_name="Alice")

        self.assertIn("SEARCH-001", result)
        self.assertNotIn("SEARCH-002", result)

    def test_search_by_driver_last_name(self):
        """Test searching loads by driver last name."""
        result = self.toolkit.search_loads(driver_name="Martinez")

        self.assertIn("SEARCH-002", result)
        self.assertNotIn("SEARCH-001", result)

    def test_search_by_street_address(self):
        """Test searching loads by street address."""
        result = self.toolkit.search_loads(street_address="Oak Street")

        self.assertIn("SEARCH-001", result)
        self.assertNotIn("SEARCH-002", result)

    def test_search_by_status(self):
        """Test searching loads by status."""
        result = self.toolkit.search_loads(status="dispatched")

        self.assertIn("SEARCH-001", result)
        self.assertNotIn("SEARCH-002", result)

    def test_search_by_billing_status(self):
        """Test searching loads by billing status."""
        result = self.toolkit.search_loads(billing_status="paperwork_pending")

        self.assertIn("SEARCH-002", result)
        self.assertNotIn("SEARCH-001", result)

    def test_combined_and_search(self):
        """Test searching with multiple criteria uses AND logic."""
        result = self.toolkit.search_loads(customer_name="Acme", status="dispatched")

        self.assertIn("SEARCH-001", result)
        self.assertNotIn("SEARCH-002", result)

    def test_combined_search_no_match(self):
        """Test combined search that matches nothing."""
        result = self.toolkit.search_loads(customer_name="Acme", status="pending")

        self.assertIn("No loads found", result)

    def test_no_criteria_error(self):
        """Test that searching with no criteria returns an error."""
        result = self.toolkit.search_loads()

        self.assertIn("Error", result)
        self.assertIn("At least one search criterion", result)

    def test_invalid_status_error(self):
        """Test that invalid status returns an error."""
        result = self.toolkit.search_loads(status="invalid_status")

        self.assertIn("Error", result)
        self.assertIn("Invalid status", result)

    def test_invalid_billing_status_error(self):
        """Test that invalid billing status returns an error."""
        result = self.toolkit.search_loads(billing_status="bad_billing")

        self.assertIn("Error", result)
        self.assertIn("Invalid billing_status", result)

    def test_no_results_message(self):
        """Test that no results returns a friendly message."""
        result = self.toolkit.search_loads(customer_name="Nonexistent Corp")

        self.assertIn("No loads found", result)

    def test_case_insensitive_customer_search(self):
        """Test that customer search is case-insensitive."""
        result = self.toolkit.search_loads(customer_name="acme")

        self.assertIn("SEARCH-001", result)

    def test_case_insensitive_driver_search(self):
        """Test that driver search is case-insensitive."""
        result = self.toolkit.search_loads(driver_name="alice")

        self.assertIn("SEARCH-001", result)

    def test_org_filtering(self):
        """Test that only loads from the scoped organization are returned."""
        # Create load in other org with same customer name pattern
        other_customer = CustomerFactory.create(
            organization=self.other_org,
            customer_name="Acme International",
        )
        LoadFactory.create(
            organization=self.other_org,
            reference_number="OTHER-001",
            customer=other_customer,
        )

        result = self.toolkit.search_loads(customer_name="Acme")

        self.assertIn("SEARCH-001", result)
        self.assertNotIn("OTHER-001", result)


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
        """Set up test data that will be shared across all test methods."""
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
        """Set up test fixtures for each test method."""
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
        """Test that planner agent can swap drivers between two loads."""
        agent = get_planner_agent(self.organization)
        response = agent.run("Swap the drivers between load LOAD-001 and LOAD-002")

        print(f"\n{'='*60}")
        print("TEST: planner_agent_swaps_drivers")
        print(f"{'='*60}")
        print(f"Response:\n{response.content}")
        print(f"{'='*60}\n")

        # Verify the response mentions the swap
        response_text = response.content.lower()
        self.assertTrue(
            "swap" in response_text or "completed" in response_text or "success" in response_text,
            f"Expected swap confirmation in response: {response.content}"
        )

        # Verify database state - drivers should be swapped
        new_assignment1 = ShipmentAssignment.objects.get(leg=self.leg1)
        new_assignment2 = ShipmentAssignment.objects.get(leg=self.leg2)

        self.assertEqual(new_assignment1.driver_id, self.driver_mike.id)
        self.assertEqual(new_assignment2.driver_id, self.driver_john.id)

    def test_planner_agent_handles_invalid_reference(self):
        """Test that planner agent handles invalid reference numbers gracefully."""
        agent = get_planner_agent(self.organization)
        response = agent.run("Swap drivers between LOAD-001 and INVALID-LOAD")

        print(f"\n{'='*60}")
        print("TEST: planner_agent_handles_invalid_reference")
        print(f"{'='*60}")
        print(f"Response:\n{response.content}")
        print(f"{'='*60}\n")

        # Should mention not found or error
        response_text = response.content.lower()
        self.assertTrue(
            "not found" in response_text or "invalid" in response_text or "error" in response_text,
            f"Expected error message in response: {response.content}"
        )

        # Original assignment should be unchanged
        assignment1 = ShipmentAssignment.objects.get(leg=self.leg1)
        self.assertEqual(assignment1.driver_id, self.driver_john.id)

    def test_lead_team_delegates_swap_to_planner(self):
        """Test that lead team delegates swap requests to planner agent."""
        team = get_lead_agent(self.organization)
        response = team.run("I need to swap drivers between LOAD-001 and LOAD-002")

        print(f"\n{'='*60}")
        print("TEST: lead_team_delegates_swap_to_planner")
        print(f"{'='*60}")
        print(f"Response:\n{response.content}")
        print(f"{'='*60}\n")

        # Verify the response mentions the swap
        response_text = response.content.lower()
        self.assertTrue(
            "swap" in response_text or "completed" in response_text or "driver" in response_text,
            f"Expected swap-related response: {response.content}"
        )

        # Verify database state - drivers should be swapped
        new_assignment1 = ShipmentAssignment.objects.get(leg=self.leg1)
        new_assignment2 = ShipmentAssignment.objects.get(leg=self.leg2)

        self.assertEqual(new_assignment1.driver_id, self.driver_mike.id)
        self.assertEqual(new_assignment2.driver_id, self.driver_john.id)
