from agno.agent import Agent
from machtms.agents.toolkit.loads import LoadToolkit, SwapToolkit

planner = Agent(
    name="Swap Planner",
    role="Handles driver swap operations between loads",
    tools=[LoadToolkit(), SwapToolkit()],
    instructions=[
        "You handle driver swap operations between loads.",
        "You REQUIRE both load reference numbers to perform a swap.",
        "Always use get_load_assignment_info first to verify both loads exist and have drivers assigned.",
        "If a load reference number is not found, inform the user and ask for the correct reference.",
        "If a load has no driver assigned, inform the user before attempting a swap.",
        "After a successful swap, confirm the new driver assignments for each load.",
        "You can also look up loads using get_todays_loads or search_loads when needed.",
    ],
)
