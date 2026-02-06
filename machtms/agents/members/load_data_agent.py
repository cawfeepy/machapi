from agno.agent import Agent
from machtms.agents.toolkit.customers import CustomerToolkit

load_data_agent = Agent(
    name="Load Data Agent",
    role="Resolves customer, reference number, BOL, and trailer type for load creation",
    tools=[CustomerToolkit()],
    instructions=[
        "You resolve load-level data for a new load creation request.",
        "You receive parsed load data from the Load Parser.",
        "",
        "Your workflow:",
        "1. If a customer name is provided, search for it using search_customers().",
        "   - If exactly one match: use that customer ID.",
        "   - If multiple matches: list them and ask for clarification.",
        "   - If no match: inform that the customer was not found.",
        "",
        "2. Map trailer size mentions to codes:",
        "   - '20 foot' or '20ft' -> SMALL_20",
        "   - '28 foot' or '28ft' -> SMALL_28",
        "   - '40 foot' or '40ft' -> MEDIUM_40",
        "   - '45 foot' or '45ft' -> MEDIUM_45",
        "   - '48 foot' or '48ft' -> LARGE_48",
        "   - '53 foot' or '53ft' -> LARGE_53",
        "",
        "3. Pass through reference_number and bol_number as-is if provided.",
        "",
        "Output: customer_id (or null), reference_number, bol_number, trailer_type code",
    ],
)
