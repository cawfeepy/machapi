"""
Test suite for the RateConParser functionality.

This module contains tests for:
1. ParsingSession model behavior (status, progress)
2. RateConDocument model behavior
3. PDF text extraction via pymupdf
4. Agent response parsing
5. Document processing tasks (with mocked S3 and agent)
6. Stale upload cleanup
7. Agent integration tests (requires OPENAI_API_KEY)
"""
import os
import uuid
from datetime import timedelta
from io import BytesIO
from unittest import skipUnless
from unittest.mock import patch, MagicMock

import pymupdf
from django.test import TestCase, override_settings
from django.utils import timezone

from machtms.backend.RateConParser.models import (
    ParsingSession,
    RateConDocument,
    ParsedRateCon,
    SessionStatus,
    DocumentStatus,
)
from machtms.backend.RateConParser.tasks import (
    extract_text_from_pdf,
    parse_agent_response,
    process_single_document,
    cleanup_stale_uploads,
)
from machtms.backend.auth.models import Organization
from machtms.core.factories import (
    ParsingSessionFactory,
    RateConDocumentFactory,
    ParsedRateConFactory,
)


def _create_pdf_buffer(text_content: str = "Sample rate confirmation text") -> BytesIO:
    """Generate an in-memory PDF with the given text."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), text_content, fontsize=12)
    buffer = BytesIO()
    doc.save(buffer)
    doc.close()
    buffer.seek(0)
    return buffer


SAMPLE_AGENT_RESPONSE_PASS = """
CLASSIFICATION: PASS
REASON:

--- BASIC INFO ---
Reference Number: RC-12345
BOL Number: BOL-67890
Customer Name: Acme Shipping Co
Trailer Type: 53' Dry Van

--- FINANCIAL INFO ---
Line Haul Rate: $2,500.00
Fuel Surcharge: $150.00
Accessorials: NONE
Total Rate: $2,650.00

--- STOPS ---
Stop 1:
  Type: PICKUP
  Address: 123 Warehouse Blvd
  City: Los Angeles
  State: CA
  Zip: 90001
  Appointment: 02/25/2026 08:00
  PO Numbers: PO-111
  Notes: Dock door #5

Stop 2:
  Type: DELIVERY
  Address: 456 Distribution Way
  City: Portland
  State: OR
  Zip: 97201
  Appointment: 02/27/2026 14:00
  PO Numbers: NONE
  Notes: NONE

--- CARRIER INFO ---
Carrier Name: Swift Logistics
MC Number: MC-123456

--- INVOICING ---
Payment Terms: Net 30
Invoice Email: billing@acme.com
"""

SAMPLE_AGENT_RESPONSE_FAIL = """
CLASSIFICATION: FAIL
REASON: This document appears to be an invoice, not a rate confirmation. It lacks pickup/delivery information and carrier details.
"""


# ============================================================================
# ParsingSession Model Tests
# ============================================================================

@override_settings(DEBUG=False)
class ParsingSessionModelTests(TestCase):
    """Tests for ParsingSession model behavior."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-000-0000",
            email="test@org.com",
        )

    def test_session_creation(self):
        session = ParsingSessionFactory(organization=self.organization)
        self.assertEqual(session.status, SessionStatus.UPLOADING)
        self.assertIsNotNone(session.created_at)

    def test_total_documents(self):
        session = ParsingSessionFactory(organization=self.organization)
        RateConDocumentFactory(session=session, organization=self.organization)
        RateConDocumentFactory(session=session, organization=self.organization)
        self.assertEqual(session.total_documents, 2)

    def test_completed_documents(self):
        session = ParsingSessionFactory(organization=self.organization)
        RateConDocumentFactory(
            session=session, organization=self.organization,
            status=DocumentStatus.PARSED,
        )
        RateConDocumentFactory(
            session=session, organization=self.organization,
            status=DocumentStatus.PENDING,
        )
        self.assertEqual(session.completed_documents, 1)

    def test_progress_calculation(self):
        session = ParsingSessionFactory(organization=self.organization)
        RateConDocumentFactory(
            session=session, organization=self.organization,
            status=DocumentStatus.PARSED,
        )
        RateConDocumentFactory(
            session=session, organization=self.organization,
            status=DocumentStatus.PENDING,
        )
        self.assertEqual(session.progress, 50.0)

    def test_progress_empty_session(self):
        session = ParsingSessionFactory(organization=self.organization)
        self.assertEqual(session.progress, 0)

    def test_recompute_status_all_parsed(self):
        session = ParsingSessionFactory(organization=self.organization)
        RateConDocumentFactory(
            session=session, organization=self.organization,
            status=DocumentStatus.PARSED,
        )
        RateConDocumentFactory(
            session=session, organization=self.organization,
            status=DocumentStatus.PARSED,
        )
        session.recompute_status()
        session.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.COMPLETED)

    def test_recompute_status_all_failed(self):
        session = ParsingSessionFactory(organization=self.organization)
        RateConDocumentFactory(
            session=session, organization=self.organization,
            status=DocumentStatus.FAILED,
        )
        session.recompute_status()
        session.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.FAILED)

    def test_recompute_status_partially_failed(self):
        session = ParsingSessionFactory(organization=self.organization)
        RateConDocumentFactory(
            session=session, organization=self.organization,
            status=DocumentStatus.PARSED,
        )
        RateConDocumentFactory(
            session=session, organization=self.organization,
            status=DocumentStatus.FAILED,
        )
        session.recompute_status()
        session.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.PARTIALLY_FAILED)

    def test_recompute_status_with_pending(self):
        """Pending docs should prevent status change."""
        session = ParsingSessionFactory(organization=self.organization)
        RateConDocumentFactory(
            session=session, organization=self.organization,
            status=DocumentStatus.PARSED,
        )
        RateConDocumentFactory(
            session=session, organization=self.organization,
            status=DocumentStatus.PENDING,
        )
        original_status = session.status
        session.recompute_status()
        session.refresh_from_db()
        # Status should not change since not all docs are terminal
        self.assertEqual(session.status, original_status)

    def test_str_representation(self):
        session = ParsingSessionFactory(organization=self.organization)
        self.assertIn("ParsingSession", str(session))


# ============================================================================
# RateConDocument Model Tests
# ============================================================================

@override_settings(DEBUG=False)
class RateConDocumentModelTests(TestCase):
    """Tests for RateConDocument model behavior."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-000-0000",
            email="test@org.com",
        )

    def test_document_creation(self):
        doc = RateConDocumentFactory(organization=self.organization)
        self.assertEqual(doc.status, DocumentStatus.PENDING)
        self.assertIsNotNone(doc.original_filename)
        self.assertIsNotNone(doc.s3_key)

    def test_parsed_content_relation(self):
        doc = RateConDocumentFactory(organization=self.organization)
        parsed = ParsedRateConFactory(
            document=doc,
            organization=self.organization,
        )
        self.assertEqual(doc.parsed_content, parsed)
        self.assertEqual(parsed.document, doc)

    def test_str_representation(self):
        doc = RateConDocumentFactory(organization=self.organization)
        self.assertIn("RateConDocument", str(doc))


# ============================================================================
# Text Extraction Tests
# ============================================================================

@override_settings(DEBUG=False)
class TextExtractionTests(TestCase):
    """Tests for PDF text extraction via pymupdf."""

    def test_extract_text_from_pdf(self):
        buffer = _create_pdf_buffer("Hello rate confirmation world")
        text = extract_text_from_pdf(buffer)
        self.assertIn("Hello rate confirmation world", text)

    def test_extract_text_from_empty_pdf(self):
        doc = pymupdf.open()
        doc.new_page(width=612, height=792)  # blank page
        buffer = BytesIO()
        doc.save(buffer)
        doc.close()
        buffer.seek(0)
        text = extract_text_from_pdf(buffer)
        self.assertEqual(text.strip(), "")

    def test_extract_text_multipage(self):
        doc = pymupdf.open()
        page1 = doc.new_page(width=612, height=792)
        page1.insert_text((72, 72), "Page 1 content", fontsize=12)
        page2 = doc.new_page(width=612, height=792)
        page2.insert_text((72, 72), "Page 2 content", fontsize=12)
        buffer = BytesIO()
        doc.save(buffer)
        doc.close()
        buffer.seek(0)
        text = extract_text_from_pdf(buffer)
        self.assertIn("Page 1 content", text)
        self.assertIn("Page 2 content", text)


# ============================================================================
# Agent Response Parsing Tests
# ============================================================================

@override_settings(DEBUG=False)
class AgentResponseParsingTests(TestCase):
    """Tests for parse_agent_response utility."""

    def test_parse_pass_response(self):
        result = parse_agent_response(SAMPLE_AGENT_RESPONSE_PASS)
        self.assertEqual(result['classification'], 'PASS')
        self.assertEqual(result['classification_reason'], '')
        self.assertIn('raw_text', result)
        self.assertIsInstance(result['structured_data'], dict)

    def test_parse_fail_response(self):
        result = parse_agent_response(SAMPLE_AGENT_RESPONSE_FAIL)
        self.assertEqual(result['classification'], 'FAIL')
        self.assertIn('invoice', result['classification_reason'].lower())

    def test_parse_extracts_reference_number(self):
        result = parse_agent_response(SAMPLE_AGENT_RESPONSE_PASS)
        data = result['structured_data']
        self.assertEqual(data.get('Reference Number'), 'RC-12345')

    def test_parse_extracts_stops(self):
        result = parse_agent_response(SAMPLE_AGENT_RESPONSE_PASS)
        data = result['structured_data']
        self.assertIn('stops', data)
        self.assertEqual(len(data['stops']), 2)

    def test_parse_extracts_carrier_info(self):
        result = parse_agent_response(SAMPLE_AGENT_RESPONSE_PASS)
        data = result['structured_data']
        self.assertEqual(data.get('Carrier Name'), 'Swift Logistics')

    def test_parse_empty_response(self):
        result = parse_agent_response("")
        self.assertEqual(result['classification'], 'PASS')
        self.assertEqual(result['structured_data'], {})


# ============================================================================
# Process Document Task Tests
# ============================================================================

@override_settings(DEBUG=False)
class ProcessDocumentTaskTests(TestCase):
    """Tests for process_single_document with mocked S3 and agent."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-000-0000",
            email="test@org.com",
        )

    def _create_pending_doc(self):
        session = ParsingSessionFactory(organization=self.organization)
        doc = RateConDocumentFactory(
            session=session,
            organization=self.organization,
            status=DocumentStatus.PENDING,
        )
        return doc

    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    @patch('machtms.agents.members.rate_con_processor.rate_con_processor')
    def test_process_document_pass(self, mock_agent, mock_download):
        doc = self._create_pending_doc()

        # Mock S3 download
        pdf_buffer = _create_pdf_buffer("Rate Confirmation RC-12345")
        mock_download.return_value = pdf_buffer

        # Mock agent response
        mock_response = MagicMock()
        mock_response.content = SAMPLE_AGENT_RESPONSE_PASS
        mock_agent.run.return_value = mock_response

        process_single_document(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.PARSED)
        self.assertIsNotNone(doc.processed_at)
        self.assertTrue(hasattr(doc, 'parsed_content'))
        self.assertTrue(doc.parsed_content.classification_passed)

    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    @patch('machtms.agents.members.rate_con_processor.rate_con_processor')
    def test_process_document_fail_classification(self, mock_agent, mock_download):
        doc = self._create_pending_doc()

        pdf_buffer = _create_pdf_buffer("This is an invoice")
        mock_download.return_value = pdf_buffer

        mock_response = MagicMock()
        mock_response.content = SAMPLE_AGENT_RESPONSE_FAIL
        mock_agent.run.return_value = mock_response

        process_single_document(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.MISCLASSIFIED)
        self.assertFalse(doc.parsed_content.classification_passed)

    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    def test_process_document_empty_pdf(self, mock_download):
        doc = self._create_pending_doc()

        # Empty PDF
        empty_doc = pymupdf.open()
        empty_doc.new_page(width=612, height=792)
        buf = BytesIO()
        empty_doc.save(buf)
        empty_doc.close()
        buf.seek(0)
        mock_download.return_value = buf

        process_single_document(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.FAILED)
        self.assertIn("No text", doc.error_message)

    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    def test_process_document_s3_error(self, mock_download):
        doc = self._create_pending_doc()
        mock_download.side_effect = Exception("S3 connection failed")

        process_single_document(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.FAILED)
        self.assertIn("S3 connection failed", doc.error_message)

    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    @patch('machtms.agents.members.rate_con_processor.rate_con_processor')
    def test_session_status_updates_after_processing(self, mock_agent, mock_download):
        """Session recomputes its status after document processing."""
        session = ParsingSessionFactory(organization=self.organization)
        doc = RateConDocumentFactory(
            session=session,
            organization=self.organization,
            status=DocumentStatus.PENDING,
        )

        pdf_buffer = _create_pdf_buffer("Rate con text")
        mock_download.return_value = pdf_buffer

        mock_response = MagicMock()
        mock_response.content = SAMPLE_AGENT_RESPONSE_PASS
        mock_agent.run.return_value = mock_response

        process_single_document(doc.pk)

        session.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.COMPLETED)


# ============================================================================
# Cleanup Task Tests
# ============================================================================

@override_settings(DEBUG=False)
class CleanupTaskTests(TestCase):
    """Tests for cleanup_stale_uploads task."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-000-0000",
            email="test@org.com",
        )

    def test_cleanup_stale_uploads(self):
        session = ParsingSessionFactory(organization=self.organization)
        stale_doc = RateConDocumentFactory(
            session=session,
            organization=self.organization,
            status=DocumentStatus.UPLOADING,
            created_at=timezone.now() - timedelta(hours=2),
        )
        fresh_doc = RateConDocumentFactory(
            session=session,
            organization=self.organization,
            status=DocumentStatus.UPLOADING,
            created_at=timezone.now(),
        )

        cleanup_stale_uploads()

        stale_doc.refresh_from_db()
        fresh_doc.refresh_from_db()
        self.assertEqual(stale_doc.status, DocumentStatus.FAILED)
        self.assertIn("timed out", stale_doc.error_message)
        self.assertEqual(fresh_doc.status, DocumentStatus.UPLOADING)

    def test_cleanup_ignores_non_uploading(self):
        session = ParsingSessionFactory(organization=self.organization)
        pending_doc = RateConDocumentFactory(
            session=session,
            organization=self.organization,
            status=DocumentStatus.PENDING,
            created_at=timezone.now() - timedelta(hours=2),
        )

        cleanup_stale_uploads()

        pending_doc.refresh_from_db()
        self.assertEqual(pending_doc.status, DocumentStatus.PENDING)


# ============================================================================
# Agent Integration Tests (requires OPENAI_API_KEY)
# ============================================================================

@skipUnless(os.environ.get('OPENAI_API_KEY'), "OPENAI_API_KEY not set")
@override_settings(DEBUG=False)
class AgentIntegrationTests(TestCase):
    """Integration tests that run the actual rate con processor agent.

    Requires OPENAI_API_KEY environment variable.
    """

    def test_agent_classifies_rate_con_text(self):
        from machtms.agents.members.rate_con_processor import rate_con_processor

        sample_text = (
            "RATE CONFIRMATION\n"
            "Reference Number: RC-99999\n"
            "BOL Number: BOL-55555\n"
            "Customer Name: Acme Corp\n"
            "Trailer Type: 53' Dry Van\n"
            "Line Haul Rate: $2,500.00\n"
            "Carrier Name: Test Carrier\n"
            "MC Number: MC-111111\n"
            "\n"
            "Pickup:\n"
            "  123 Main St, Los Angeles, CA 90001\n"
            "  Appointment: 03/01/2026 08:00\n"
            "\n"
            "Delivery:\n"
            "  456 Oak Ave, Portland, OR 97201\n"
            "  Appointment: 03/03/2026 14:00\n"
        )

        response = rate_con_processor.run(
            sample_text,
            session_id=str(uuid.uuid4()),
        )

        response_text = response.content
        self.assertIn("CLASSIFICATION", response_text.upper())
        # Should classify as PASS since it has clear rate con characteristics
        parsed = parse_agent_response(response_text)
        self.assertIn(parsed['classification'], ['PASS', 'FAIL'],
                       "Classification must be PASS or FAIL")

    def test_agent_rejects_non_rate_con(self):
        from machtms.agents.members.rate_con_processor import rate_con_processor

        sample_text = (
            "GROCERY LIST\n"
            "1. Milk\n"
            "2. Eggs\n"
            "3. Bread\n"
        )

        response = rate_con_processor.run(
            sample_text,
            session_id=str(uuid.uuid4()),
        )

        response_text = response.content
        parsed = parse_agent_response(response_text)
        self.assertEqual(parsed['classification'], 'FAIL')


# ============================================================================
# Real PDF Integration Tests (requires OPENAI_API_KEY + test_documents/)
# ============================================================================

TEST_DOCUMENTS_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'test_documents'
)


def _has_test_documents():
    """Check if test_documents directory exists and has PDFs."""
    return (
        os.path.isdir(TEST_DOCUMENTS_DIR)
        and any(f.endswith('.pdf') for f in os.listdir(TEST_DOCUMENTS_DIR))
    )


@skipUnless(
    os.environ.get('OPENAI_API_KEY') and _has_test_documents(),
    "OPENAI_API_KEY not set or test_documents/ missing"
)
@override_settings(DEBUG=False)
class RealPDFIntegrationTests(TestCase):
    """Integration tests that parse actual rate confirmation PDFs.

    Requires:
    - OPENAI_API_KEY environment variable
    - machtms/test_documents/ directory with at least one PDF
    """

    def _get_pdf_paths(self):
        """Return list of PDF file paths in test_documents/."""
        return [
            os.path.join(TEST_DOCUMENTS_DIR, f)
            for f in sorted(os.listdir(TEST_DOCUMENTS_DIR))
            if f.endswith('.pdf')
        ]

    def test_extract_text_from_real_pdf(self):
        """Verify pymupdf can extract text from the real PDFs."""
        for pdf_path in self._get_pdf_paths():
            with open(pdf_path, 'rb') as f:
                buf = BytesIO(f.read())
            text = extract_text_from_pdf(buf)
            self.assertTrue(
                len(text.strip()) > 100,
                f"Expected substantial text from {os.path.basename(pdf_path)}, got {len(text)} chars"
            )
            print(f"\n--- Text from {os.path.basename(pdf_path)} ({len(text)} chars) ---")
            print(text[:500])

    def test_agent_parses_real_rate_con(self):
        """Send real PDF text to the agent and inspect the parsed output."""
        from machtms.agents.members.rate_con_processor import rate_con_processor

        for pdf_path in self._get_pdf_paths():
            filename = os.path.basename(pdf_path)
            with open(pdf_path, 'rb') as f:
                buf = BytesIO(f.read())
            text = extract_text_from_pdf(buf)

            print(f"\n{'='*70}")
            print(f"Processing: {filename}")
            print(f"{'='*70}")

            response = rate_con_processor.run(
                text,
                session_id=str(uuid.uuid4()),
            )

            response_text = response.content
            print(f"\n--- Agent Raw Response ---")
            print(response_text)

            parsed = parse_agent_response(response_text)

            print(f"\n--- Parsed Result ---")
            print(f"Classification: {parsed['classification']}")
            if parsed['classification_reason']:
                print(f"Reason: {parsed['classification_reason']}")
            print(f"Structured Data Keys: {list(parsed['structured_data'].keys())}")

            for key, value in parsed['structured_data'].items():
                if key == 'stops':
                    print(f"\nStops ({len(value)}):")
                    for stop in value:
                        print(f"  Stop {stop.get('stop_number', '?')}: {stop}")
                else:
                    print(f"  {key}: {value}")

            # Basic assertions
            self.assertIn(parsed['classification'], ['PASS', 'FAIL'])
            if parsed['classification'] == 'PASS':
                data = parsed['structured_data']
                self.assertTrue(
                    len(data) > 0,
                    f"Expected structured data for {filename}"
                )

    def test_full_pipeline_with_real_pdf(self):
        """Test the complete pipeline: extract -> agent -> parse -> create record."""
        from machtms.core.factories import ParsingSessionFactory, RateConDocumentFactory
        from machtms.agents.members.rate_con_processor import rate_con_processor

        pdf_path = self._get_pdf_paths()[0]
        filename = os.path.basename(pdf_path)

        with open(pdf_path, 'rb') as f:
            buf = BytesIO(f.read())
        text = extract_text_from_pdf(buf)

        # Create session + document records
        session = ParsingSessionFactory(status=SessionStatus.PROCESSING)
        doc = RateConDocumentFactory(
            session=session,
            organization=session.organization,
            original_filename=filename,
            status=DocumentStatus.PROCESSING,
        )

        # Run agent
        response = rate_con_processor.run(
            text,
            session_id=str(uuid.uuid4()),
        )
        response_text = response.content
        parsed = parse_agent_response(response_text)

        # Create ParsedRateCon record
        parsed_record = ParsedRateCon.objects.create(
            organization=session.organization,
            document=doc,
            raw_text=parsed['raw_text'],
            structured_data=parsed['structured_data'],
            classification_passed=(parsed['classification'] == 'PASS'),
            classification_reason=parsed['classification_reason'],
        )

        # Update document status
        if parsed['classification'] == 'PASS':
            doc.status = DocumentStatus.PARSED
        else:
            doc.status = DocumentStatus.MISCLASSIFIED
        doc.processed_at = timezone.now()
        doc.save()

        # Verify
        doc.refresh_from_db()
        self.assertIn(doc.status, [DocumentStatus.PARSED, DocumentStatus.MISCLASSIFIED])
        self.assertTrue(hasattr(doc, 'parsed_content'))
        self.assertEqual(doc.parsed_content.pk, parsed_record.pk)

        print(f"\n--- Full Pipeline Result for {filename} ---")
        print(f"Document Status: {doc.status}")
        print(f"Classification: {'PASS' if parsed_record.classification_passed else 'FAIL'}")
        print(f"Structured Data: {parsed_record.structured_data}")


# ============================================================================
# End-to-End: rate_con_processor → ratecon_load_creator
# ============================================================================

@skipUnless(
    os.environ.get('OPENAI_API_KEY') and _has_test_documents(),
    "OPENAI_API_KEY not set or test_documents/ missing"
)
class RateConToLoadEndToEndTests(TestCase):
    """End-to-end test: parse a real PDF then create a load from the parsed output.

    Chain: PDF → extract text → rate_con_processor → ratecon_load_creator → Load in DB
    """

    def setUp(self):
        self.organization = Organization.objects.create(
            company_name="E2E Test Org",
            phone="555-000-0000",
            email="e2e@test.com",
        )

    def _get_first_pdf_path(self):
        return os.path.join(
            TEST_DOCUMENTS_DIR,
            sorted(f for f in os.listdir(TEST_DOCUMENTS_DIR) if f.endswith('.pdf'))[0],
        )

    def test_parse_then_create_load(self):
        """Parse a real rate con PDF, then have the load creator agent build a load."""
        from machtms.agents.members.rate_con_processor import rate_con_processor
        from machtms.agents.members.ratecon_load_creator import ratecon_load_creator
        from machtms.backend.loads.models import Load

        pdf_path = self._get_first_pdf_path()
        filename = os.path.basename(pdf_path)

        # Step 1: Extract text from real PDF
        with open(pdf_path, 'rb') as f:
            buf = BytesIO(f.read())
        text = extract_text_from_pdf(buf)
        self.assertTrue(len(text.strip()) > 100)

        print(f"\n{'='*70}")
        print(f"E2E Test: {filename}")
        print(f"{'='*70}")

        # Step 2: Run rate_con_processor to get structured output
        parse_response = rate_con_processor.run(
            text,
            session_id=str(uuid.uuid4()),
        )
        parsed_text = parse_response.content
        print(f"\n--- rate_con_processor output ---")
        print(parsed_text)

        parsed = parse_agent_response(parsed_text)
        self.assertEqual(parsed['classification'], 'PASS',
                         f"Expected PASS classification for {filename}")

        # Step 3: Feed the parsed output to ratecon_load_creator
        loads_before = Load.objects.filter(organization=self.organization).count()

        creator_prompt = (
            f"Create a load from this parsed rate confirmation data:\n\n{parsed_text}"
        )

        creator_response = ratecon_load_creator.run(
            creator_prompt,
            session_id=str(uuid.uuid4()),
            dependencies={"organization": self.organization},
        )
        creator_output = creator_response.content
        print(f"\n--- ratecon_load_creator output ---")
        print(creator_output)

        # Step 4: Verify a load was created
        loads_after = Load.objects.filter(organization=self.organization).count()
        self.assertEqual(loads_after, loads_before + 1,
                         "Expected exactly one new load to be created")

        load = Load.objects.filter(organization=self.organization).order_by('-pk').first()
        print(f"\n--- Created Load ---")
        print(f"  ID: {load.pk}")
        print(f"  Reference: {load.reference_number}")
        print(f"  BOL: {load.bol_number}")
        print(f"  Trailer: {load.trailer_type}")
        print(f"  Status: {load.status}")
        print(f"  Customer: {load.customer}")

        # Verify load has legs and stops
        legs = load.legs.all()
        self.assertTrue(legs.exists(), "Load should have at least one leg")

        for leg in legs:
            stops = leg.stops.all().order_by('stop_number')
            self.assertTrue(stops.exists(), "Leg should have stops")
            print(f"  Leg {leg.pk}:")
            for stop in stops:
                addr = stop.address
                print(f"    Stop {stop.stop_number}: {stop.get_action_display()} ({stop.action})"
                      f" @ {addr.street}, {addr.city}, {addr.state} {addr.zip_code}"
                      f" | {stop.start_range}")

        # Basic sanity: reference number should be populated
        self.assertTrue(load.reference_number, "Load should have a reference number")
