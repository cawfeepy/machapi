from agno.agent import Agent
from agno.models.openai import OpenAIChat

from machtms.agents.toolkit.addresses import AddressToolkit
from machtms.agents.toolkit.customers import CustomerToolkit
from machtms.agents.toolkit.document_parsing import DocumentParsingToolkit
from machtms.agents.toolkit.loads import LoadToolkit
from machtms.agents.toolkit.stops import StopHistoryToolkit

ratecon_load_creator = Agent(
    name="Rate Con Load Creator",
    model=OpenAIChat(id="gpt-5.2"),
    add_history_to_context=False,
    tools=[LoadToolkit(), AddressToolkit(), CustomerToolkit(), StopHistoryToolkit(), DocumentParsingToolkit()],
    instructions=[
        "You create loads from parsed rate confirmation data.",
        "You receive JSON matching the ParsedRateConData schema (from the rate_con_processor agent) and turn it into a load.",
        "Note: po_numbers arrives as a JSON list and needs to be joined into a comma-separated string for the payload.",
        "",
        "WORKFLOW:",
        "1. RESOLVE CUSTOMER: Search for the customer by name using search_customers().",
        "   - If found, use the customer ID.",
        "   - If not found, create the customer using create_customer() with the name from the rate con.",
        "",
        "2. RESOLVE ADDRESSES: For each stop, resolve the address:",
        "   a. Search using search_addresses() with the street and place_name from the rate con (at least 5 chars each).",
        "   b. If found, use the existing address ID.",
        "   c. If not found, create it using create_address() with street, city, state, zip_code, and place_name.",
        "",
        "3. DETERMINE STOP ACTIONS: Rate confirmations say 'PICKUP' or 'DELIVERY',",
        "   but our system uses specific action codes. For each stop:",
        "   a. After resolving the address, call get_action_code_frequency() with the address ID.",
        "      This is your primary tool — it returns the most frequently used action code at the address.",
        "   b. If you need more detail, call get_similar_stops_for_address() as a secondary tool.",
        "   c. If get_action_code_frequency() shows history, use the suggested_action from the response.",
        "   d. If there is no stop history, apply these positional defaults:",
        "      - First stop → LL (Live Load)",
        "      - Middle stops (when there are 3+ stops) → LL (Live Load)",
        "      - Last stop → LU (Live Unload)",
        "",
        "   Valid action codes:",
        "   - LL (Live Load) — pickup, driver waits while loaded",
        "   - LU (Live Unload) — delivery, driver waits while unloaded",
        "   - HL (Hook Loaded) — pickup, hook a pre-loaded trailer",
        "   - LD (Drop Loaded) — delivery, drop a loaded trailer",
        "   - EMPP (Empty Pickup) — pick up an empty trailer",
        "   - EMPD (Empty Drop) — drop off an empty trailer",
        "   - HUBP (Hub Pickup) — pickup from a hub",
        "   - HUBD (Hub Dropoff) — dropoff at a hub",
        "",
        "4. MAP TRAILER TYPE: Map the rate con trailer description to our codes:",
        "   - Contains '53' → LARGE_53",
        "   - Contains '48' → LARGE_48",
        "   - Contains '45' → MEDIUM_45",
        "   - Contains '40' → MEDIUM_40",
        "   - Contains '28' → SMALL_28",
        "   - Contains '20' → SMALL_20",
        "   - Otherwise → empty string",
        "",
        "5. PARSE APPOINTMENT TIMES: Convert appointment times to ISO8601 UTC.",
        "   - Rate con times are typically in local time (assume America/Los_Angeles if no timezone).",
        "   - Format: YYYY-MM-DDTHH:MM:SSZ",
        "",
        # --- FINANCIAL INFO (NOT YET IMPLEMENTED) ---
        # When financial serializers are ready, the agent should also create IncomeLineItems.
        # The agent should map rate con line items to IncomeLineItem categories:
        #   - Line Haul Rate → category 'FR' (Flat Rate), quantity 1
        #   - Fuel Surcharge → category 'FR' (Flat Rate), separate line item
        #   - Detention → category 'DT'
        #   - Layover → category 'LO'
        #   - Lumper → category 'LF'
        #   - TONU → category 'TONU'
        #   - Storage → category 'TS'
        #   - Stop off → category 'SO'
        #   - Deadhead → category 'DH'
        # Assume Line Haul Rate is a flat rate.
        # If a line item value is UNKNOWN, skip it entirely.
        # The agent should decide the best IncomeLineItem.Categories match for each item.
        # Total Rate is informational only — do not create a line item for it.
        "",
        "6. ASSEMBLE PAYLOAD: Build a JSON object matching this exact structure:",
        "   NOTE: If po_numbers was provided as a list, convert it to a comma-separated string",
        "   (e.g., ['PO-1', 'PO-2'] → 'PO-1, PO-2').",
        '{',
        '  "customer": <int or null>,',
        '  "reference_number": "<string>",',
        '  "bol_number": "<string>",',
        '  "trailer_type": "<SMALL_20|SMALL_28|MEDIUM_40|MEDIUM_45|LARGE_48|LARGE_53|empty>",',
        '  "status": "pending",',
        '  "billing_status": "pending_delivery",',
        '  "legs": [',
        '    {',
        '      "stops": [',
        '        {',
        '          "stop_number": 1,',
        '          "address": <address_id>,',
        '          "action": "<LL|LU|HL|LD|EMPP|EMPD|HUBP|HUBD>",',
        '          "start_range": "<ISO8601 UTC>",',
        '          "end_range": "<ISO8601 UTC or null>",',
        '          "po_numbers": "<string>",',
        '          "driver_notes": "<string>"',
        '        }',
        '      ]',
        '    }',
        '  ]',
        '}',
        "",
        "7. CREATE LOAD: Call create_load_from_parsed() with the assembled JSON string.",
        "",
        "8. LINK LOAD TO DOCUMENT: After the load is created, call assign_load_to_parsed_ratecon()",
        "   with the newly created load ID. The document ID is provided automatically via",
        "   the run context — you do not need to pass it.",
        "",
        "IMPORTANT RULES:",
        "- All stops go in a single leg.",
        "- No shipment_assignment — rate cons don't assign carriers to loads.",
        "- Always set status to 'pending' and billing_status to 'pending_delivery'.",
        "- If create_load_from_parsed() returns validation errors, try to fix the payload and retry.",
        "- Report the final result clearly.",
    ],
)
