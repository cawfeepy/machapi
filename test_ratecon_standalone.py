#!/usr/bin/env python
"""
Standalone script to test the rate_con_processor agent on a real PDF.
Uses raw text extraction mode (no Docker required).
"""
import sys
import os
import json
import pymupdf
from pathlib import Path

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")
sys.path.insert(0, "/Users/me/mshared/mtms/app/backend/machapi")

import django
django.setup()

from machtms.agents.members.rate_con_processor import rate_con_processor
from agno.run.base import RunContext

# Get test PDF
pdf_path = Path("/Users/me/mshared/mtms/app/backend/machapi/machtms/test_documents/RXO_34058_16654538.pdf")

if not pdf_path.exists():
    print(f"Error: Test PDF not found at {pdf_path}")
    sys.exit(1)

print(f"\n{'='*80}")
print(f"RATE CON PARSER - USE_RAW_TEXT MODE")
print(f"{'='*80}")
print(f"Test Document: {pdf_path.name}\n")

# Extract text from PDF (raw text mode)
print("Step 1: Extracting text from PDF...")
doc = pymupdf.open(pdf_path)
page_count = len(doc)
extracted_text = ""
for page_num in range(page_count):
    page = doc[page_num]
    extracted_text += page.get_text() + "\n"
doc.close()

print(f"  ✓ Extracted {len(extracted_text)} characters from {page_count} page(s)")

# Create mock run context (no database needed)
print("\nStep 2: Preparing agent context...")

class MockOrganization:
    """Mock organization object without requiring database access."""
    def __init__(self):
        self.company_name = "Test Organization"
        self.phone = "555-0000"
        self.email = "test@example.com"
        self.pk = 1

organization = MockOrganization()
run_context = RunContext(
    run_id="test-standalone",
    session_id="test-session",
    dependencies={"organization": organization}
)
print(f"  ✓ Organization: {organization.company_name}")

# Run the agent
print("\nStep 3: Running rate_con_processor agent...")
import uuid
result = rate_con_processor.run(
    extracted_text,
    session_id=str(uuid.uuid4()),
    dependencies={"organization": organization}
)
print("  ✓ Agent execution complete\n")

# Format and display output
print(f"{'='*80}")
print("PARSED RATE CONFIRMATION DATA")
print(f"{'='*80}\n")

if hasattr(result, 'content'):
    parsed_data = result.content
else:
    parsed_data = result

# Convert Pydantic model to dict if needed
if hasattr(parsed_data, 'model_dump'):
    parsed_data = parsed_data.model_dump()
elif hasattr(parsed_data, '__dict__'):
    # Try to convert to dict for display
    parsed_data_str = str(parsed_data)
    try:
        # If it's a Pydantic repr, try to parse it
        import ast
        parsed_data = ast.literal_eval(parsed_data_str.replace("ParsedStop(", "dict(").replace("ParsedRateConData(", "dict("))
    except:
        pass

if isinstance(parsed_data, dict):
    print("╔════════════════════════════════════════════════════════════════════════════════╗")
    print("║ CLASSIFICATION RESULT                                                          ║")
    print("╚════════════════════════════════════════════════════════════════════════════════╝")
    print(f"Classification: {parsed_data.get('classification', 'N/A')}")
    if parsed_data.get('classification_reason'):
        print(f"Reason: {parsed_data.get('classification_reason')}")
    print()
    
    if parsed_data.get('classification') == 'PASS':
        print("╔════════════════════════════════════════════════════════════════════════════════╗")
        print("║ EXTRACTED DATA                                                                 ║")
        print("╚════════════════════════════════════════════════════════════════════════════════╝")
        print(f"Reference #:    {parsed_data.get('reference_number', 'N/A')}")
        print(f"BOL #:          {parsed_data.get('bol_number', 'N/A')}")
        print(f"Customer:       {parsed_data.get('customer_name', 'N/A')}")
        print(f"Trailer Type:   {parsed_data.get('trailer_type', 'N/A')}")
        print()
        
        print("╔════════════════════════════════════════════════════════════════════════════════╗")
        print("║ STOPS                                                                          ║")
        print("╚════════════════════════════════════════════════════════════════════════════════╝")
        stops = parsed_data.get('stops', [])
        for i, stop in enumerate(stops, 1):
            print(f"\n▸ Stop {i} - {stop.get('stop_type', 'N/A')}")
            if stop.get('place_name'):
                print(f"  Location:      {stop.get('place_name')}")
            print(f"  Address:       {stop.get('street_address', 'N/A')}")
            print(f"                 {stop.get('city', 'N/A')}, {stop.get('state', 'N/A')} {stop.get('zip_code', 'N/A')}")
            print(f"  Appointment:   {stop.get('appointment', 'N/A')}")
            if stop.get('po_numbers'):
                po_str = ', '.join(str(p) for p in stop.get('po_numbers', []))
                print(f"  PO Numbers:    {po_str}")
            if stop.get('notes'):
                print(f"  Notes:         {stop.get('notes')}")
        
        print()
        print("╔════════════════════════════════════════════════════════════════════════════════╗")
        print("║ BILLING                                                                        ║")
        print("╚════════════════════════════════════════════════════════════════════════════════╝")
        print(f"Standard Pay:   {parsed_data.get('invoice_email_standard_pay', 'UNKNOWN')}")
        print(f"Quick Pay:      {parsed_data.get('invoice_email_quick_pay', 'UNKNOWN')}")
else:
    print("RAW AGENT OUTPUT:")
    print(json.dumps(parsed_data, indent=2, default=str))

print(f"\n{'='*80}\n")
