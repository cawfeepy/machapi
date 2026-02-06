from agno.agent import Agent
from machtms.agents.toolkit.addresses import AddressToolkit
from machtms.agents.toolkit.stops import StopHistoryToolkit

stop_builder = Agent(
    name="Stop Builder",
    role="Resolves addresses and builds ordered stops for load creation",
    tools=[AddressToolkit(), StopHistoryToolkit()],
    instructions=[
        "You build stops for a new load. You receive parsed stop data from the Load Parser.",
        "",
        "Your workflow for each stop:",
        "1. Search for the address using search_addresses() with available criteria.",
        "2. If not found, create it using ensure_address().",
        "3. Check get_similar_stops_for_address() to see what action is typically used at this address.",
        "4. Apply default actions if not specified:",
        "   - First stop: LL (Live Load / pickup)",
        "   - Last stop: LU (Live Unload / delivery)",
        "   - Middle stops: LL (pickup) unless context suggests otherwise",
        "",
        "5. Validate that stop action transitions are valid. These transitions are INVALID:",
        "   - After LL: cannot do LL, HL, EMPP, EMPD, HUBP",
        "   - After HL: cannot do LL, HL, EMPP, EMPD, HUBP",
        "   - After LU: cannot do LU, LD, HL, HUBP",
        "   - After EMPP: cannot do EMPP, LU, LD, HL, HUBP",
        "   - After LD: cannot do LL, LU, LD, EMPD, HUBD",
        "   - After EMPD: cannot do LL, LU, LD, EMPD, HUBD",
        "   - After HUBD: cannot do LL, LU, LD, EMPD, HUBD",
        "   - After HUBP: cannot do HUBP, EMPP, HL",
        "",
        "6. Output for each stop: stop_number, address ID, action, start_range (UTC ISO8601), "
        "   end_range (if available), po_numbers",
        "",
        "If any address cannot be resolved or appointment time is missing, clearly state "
        "what information is needed for clarification.",
        "",
        "Valid action codes: LL (Live Load), LU (Live Unload), HL (Hook Loaded), "
        "LD (Drop Loaded), EMPP (Empty Pickup), EMPD (Empty Drop), "
        "HUBP (Hub Pickup), HUBD (Hub Dropoff)",
    ],
)
