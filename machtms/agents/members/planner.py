from agno.agent import Agent
from agno.models.openai import OpenAIChat

from machtms.agents.toolkits import SwapToolkit


def get_planner_agent(organization):
    """Factory function to create organization-scoped planner agent."""
    return Agent(
        name="Swap Planner",
        role="Handles driver swap operations between loads",
        model=OpenAIChat(id="gpt-5.2"),
        tools=[SwapToolkit(organization=organization)],
        instructions=[
            "You handle driver swap operations between loads.",
            "You REQUIRE both load reference numbers to perform a swap.",
            "Always use get_load_assignment_info first to verify both loads exist and have drivers assigned.",
            "If a load reference number is not found, inform the user and ask for the correct reference.",
            "If a load has no driver assigned, inform the user before attempting a swap.",
            "After a successful swap, confirm the new driver assignments for each load.",
        ],
    )
