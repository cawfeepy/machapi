from agno.models.openai import OpenAIChat
from agno.team import Team

from machtms.agents.toolkit.loads import LoadToolkit
from .load_parser import load_parser
from .stop_builder import stop_builder
from .load_data_agent import load_data_agent
from .carrier_assignment_agent import carrier_assignment_agent

load_creation_team = Team(
    name="Load Creation Team",
    model=OpenAIChat(id="gpt-5.2"),
    members=[load_parser, stop_builder, load_data_agent, carrier_assignment_agent],
    tools=[LoadToolkit()],
    instructions=[
        "You are the Load Creation coordinator. You orchestrate the creation of new loads.",
        "",
        "ORCHESTRATION FLOW:",
        "1. Receive a natural language request to create a load.",
        "2. Delegate to Load Parser to extract structured data from the request.",
        "3. Based on the parsed output, delegate in parallel to:",
        "   - Stop Builder: to resolve addresses and build stops",
        "   - Load Data Agent: to resolve customer, trailer type, etc.",
        "   - Carrier Assignment Agent: to resolve carrier and driver",
        "4. Collect results from all agents.",
        "5. If any agent needs clarification, compile ALL clarification needs into ONE "
        "   user-facing message. Remember which agent needs which clarification.",
        "6. On user response, re-delegate only the relevant parts.",
        "7. Once all data is resolved, assemble the final JSON payload.",
        "",
        "PAYLOAD ASSEMBLY:",
        "Construct a JSON object matching this structure and call create_load():",
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
        '          "po_numbers": "",',
        '          "driver_notes": ""',
        '        }',
        '      ],',
        '      "shipment_assignment": {',
        '        "carrier": <carrier_id>,',
        '        "driver": <driver_id>',
        '      }',
        '    }',
        '  ]',
        '}',
        "",
        "IMPORTANT NOTES:",
        "- All stops go in a single leg unless the user explicitly mentions multiple legs.",
        "- The shipment_assignment is optional; omit it if no carrier/driver was resolved.",
        "- Always set status to 'pending' and billing_status to 'pending_delivery' for new loads.",
        "- After calling create_load(), report the result to the user.",
        "- If create_load() returns validation errors, try to fix the payload and retry.",
    ],
)
