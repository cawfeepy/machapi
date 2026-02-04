"""
Test suite for the Swap Agent functionality.

This module contains tests for:
1. SwapToolkit functionality
2. Agent creation
3. Agent integration tests (requires OPENAI_API_KEY)
"""
import os
from unittest import skipUnless

from django.test import TestCase, override_settings

from machtms.agents.members import get_lead_agent, get_planner_agent
from machtms.agents.toolkits import SwapToolkit
from machtms.backend.auth.models import Organization
from machtms.backend.legs.models import ShipmentAssignment
from machtms.core.factories import (
    CarrierFactory,
    DriverFactory,
    LegFactory,
    LoadFactory,
    ShipmentAssignmentFactory,
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
        self.assertEqual(len(team.members), 1)

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
