from agno.models.openai import OpenAIChat
from agno.team import Team

from .planner import get_planner_agent


def get_lead_agent(organization):
    """Factory function to create organization-scoped lead agent."""
    return Team(
        name="TMS Lead Agent",
        model=OpenAIChat(id="gpt-4o"),
        members=[get_planner_agent(organization)],
        instructions=[
            "You are the lead coordinator for TMS operations.",
            "Route swap and driver exchange queries to the Swap Planner.",
            "If the user wants to swap drivers between loads, delegate to Swap Planner.",
            "Ensure the user provides both load reference numbers before delegating.",
        ],
    )
