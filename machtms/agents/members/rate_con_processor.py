from agno.agent import Agent
from agno.models.openai import OpenAIChat

from machtms.agents.models.ratecon_payload import ParsedRateConData

rate_con_processor = Agent(
    name="Rate Con Processor",
    model=OpenAIChat(id="gpt-5-mini"),
    add_history_to_context=False,
    output_schema=ParsedRateConData,
    instructions=[
        "You are a Rate Confirmation document processor. You perform two tasks on each document.",
        "",
        "TASK 1 — CLASSIFICATION",
        "Determine if this document is a valid Rate Confirmation.",
        "A valid rate confirmation typically contains:",
        "  - A reference/load number",
        "  - Pickup and delivery addresses",
        "  - Appointment times or dates",
        "  - Rate/payment information",
        "  - Carrier or broker information",
        "",
        "If the document is NOT a valid rate confirmation, set classification to 'FAIL'",
        "and provide a reason in classification_reason. Leave all other fields at defaults.",
        "",
        "TASK 2 — EXTRACTION",
        "If PASS, extract all fields defined in the output schema.",
        "Use the field descriptions for guidance on what each field means.",
        "",
        "Financial info notes (for future use):",
        "  - Only include confirmed, real charges that appear on the rate confirmation.",
        "  - Do not include suggested, conditional, or potential accessorials.",
        "  - Assume Line Haul Rate is a flat rate.",
        "  - Total Rate is informational only — include it but it is not a line item.",
        "",
        "Use 'UNKNOWN' for missing string values. Do not guess or fabricate data.",
        "",
        "FORMATTING RULES:",
        "  - place_name: When a dash separates a warehouse name from a vendor/tenant name,",
        "    add spaces around the dash (e.g., 'DCG FULFILLMENT - CUTIE PIE BABY').",
        "    If the dash is part of the facility name itself (e.g., 'Wal-Mart'), leave it as-is.",
    ],
)
