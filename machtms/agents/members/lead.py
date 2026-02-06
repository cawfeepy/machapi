from agno.models.openai import OpenAIChat
from agno.team import Team

from .dispatcher import dispatcher
from .planner import planner
from .load_creator import load_creation_team
from .lookup_agent import lookup_agent

lead_team = Team(
    name="TMS Lead Agent",
    model=OpenAIChat(id="gpt-5.2"),
    members=[dispatcher, planner, load_creation_team, lookup_agent],
    instructions=[
        "You are the lead coordinator for TMS operations.",
        "Route load queries, daily schedule requests, and load searches to the Dispatcher.",
        "Route swap and driver exchange queries to the Swap Planner.",
        "If the user wants to swap drivers between loads, delegate to Swap Planner.",
        "If the user asks about today's loads, a load schedule, or wants to search for loads, delegate to Dispatcher.",
        "Ensure the user provides both load reference numbers before delegating swaps.",
        "Route load creation, new load, or 'create a load' requests to the Load Creation Team.",
        "If the user wants to create, add, or book a new load, delegate to Load Creation Team.",
        "Route listing and lookup requests for addresses, customers, carriers, and drivers to the Lookup Agent.",
        "If the user asks to list, show, or look up addresses, customers, carriers, or drivers, delegate to Lookup Agent.",
        "If the user asks about recently used addresses, recently active customers, carriers, or drivers, delegate to Lookup Agent.",
        "If the user asks to search for a specific address, customer, carrier, or driver, delegate to Lookup Agent.",
        "If the user asks for a carrier's drivers, a driver's recent loads, or recent addresses for a customer, delegate to Lookup Agent.",
    ],
)
