from agno.models.openai import OpenAIChat
from agno.team import Team

from .dispatcher import dispatcher
from .planner import planner

lead_team = Team(
    name="TMS Lead Agent",
    model=OpenAIChat(id="gpt-5.2"),
    members=[dispatcher, planner],
    instructions=[
        "You are the lead coordinator for TMS operations.",
        "Route load queries, daily schedule requests, and load searches to the Dispatcher.",
        "Route swap and driver exchange queries to the Swap Planner.",
        "If the user wants to swap drivers between loads, delegate to Swap Planner.",
        "If the user asks about today's loads, a load schedule, or wants to search for loads, delegate to Dispatcher.",
        "Ensure the user provides both load reference numbers before delegating swaps.",
    ],
)
