"""
Test suite for the RateConParser functionality.

This module contains tests for:
1. ParsingSession model behavior (status, progress)
2. RateConDocument model behavior
3. PDF text extraction via LiteParse CLI
4. Agent response parsing
5. Document processing tasks (with mocked S3 and agent)
6. Stale upload cleanup
7. Agent integration tests (requires OPENAI_API_KEY)
"""
import os
import tempfile
import uuid
from datetime import timedelta
from io import BytesIO
from unittest import skipUnless
from unittest.mock import patch, MagicMock

from fpdf import FPDF
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from machtms.backend.RateConParser.models import (
    ParsingSession,
    RateConDocument,
    SessionStatus,
    DocumentStatus,
)
from machtms.agents.models.ratecon_payload import ParsedRateConData, ParsedStop
from machtms.backend.RateConParser.tasks import (
    extract_text_from_pdf,
    send_pdf_url_to_agent,
    process_single_document,
)
from machtms.backend.auth.models import Organization
from machtms.core.factories import (
    ParsingSessionFactory,
    RateConDocumentFactory,
)


def _create_pdf_buffer(text_content: str = "Sample rate confirmation text") -> BytesIO:
    """Generate an in-memory PDF with the given text using fpdf2."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.text(72, 72, text_content)
    buffer = BytesIO(pdf.output())
    return buffer


def _create_pdf_tmp_file(text_content: str = "Sample rate confirmation text") -> str:
    """Generate a PDF with the given text and return its temp file path."""
    buffer = _create_pdf_buffer(text_content)
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(buffer.read())
    tmp.close()
    return tmp.name


def _create_empty_pdf_buffer() -> BytesIO:
    """Generate an in-memory PDF with a blank page (no text)."""
    pdf = FPDF()
    pdf.add_page()
    buffer = BytesIO(pdf.output())
    return buffer


def _create_multipage_pdf_buffer(pages: list[str]) -> BytesIO:
    """Generate an in-memory PDF with one page per text entry."""
    pdf = FPDF()
    pdf.set_font("Helvetica", size=12)
    for text in pages:
        pdf.add_page()
        pdf.text(72, 72, text)
    buffer = BytesIO(pdf.output())
    return buffer


def _prettify_parsed_data(parsed_data):
    """Pretty-print parsed rate confirmation data."""
    import json
    
    # Convert Pydantic model to dict if needed
    if hasattr(parsed_data, 'model_dump'):
        data_dict = parsed_data.model_dump()
    elif hasattr(parsed_data, '__dict__'):
        data_dict = parsed_data.__dict__
    else:
        data_dict = parsed_data
    
    output = []
    output.append("\n" + "="*80)
    output.append("PARSED RATE CONFIRMATION DATA")
    output.append("="*80)
    
    # Classification
    output.append("\n╔" + "="*78 + "╗")
    output.append("║ CLASSIFICATION RESULT" + " "*57 + "║")
    output.append("╚" + "="*78 + "╝")
    output.append(f"Classification: {data_dict.get('classification', 'N/A')}")
    if data_dict.get('classification_reason'):
        output.append(f"Reason: {data_dict.get('classification_reason')}")
    
    if data_dict.get('classification') == 'PASS':
        # Extracted Data
        output.append("\n╔" + "="*78 + "╗")
        output.append("║ EXTRACTED DATA" + " "*63 + "║")
        output.append("╚" + "="*78 + "╝")
        output.append(f"Reference #:    {data_dict.get('reference_number', 'N/A')}")
        output.append(f"BOL #:          {data_dict.get('bol_number', 'N/A')}")
        output.append(f"Customer:       {data_dict.get('customer_name', 'N/A')}")
        output.append(f"Trailer Type:   {data_dict.get('trailer_type', 'N/A')}")
        
        # Stops
        output.append("\n╔" + "="*78 + "╗")
        output.append("║ STOPS" + " "*72 + "║")
        output.append("╚" + "="*78 + "╝")
        stops = data_dict.get('stops', [])
        for i, stop in enumerate(stops, 1):
            output.append(f"\n▸ Stop {i} - {stop.get('stop_type', 'N/A')}")
            if stop.get('place_name'):
                output.append(f"  Location:      {stop.get('place_name')}")
            output.append(f"  Address:       {stop.get('street_address', 'N/A')}")
            output.append(f"                 {stop.get('city', 'N/A')}, {stop.get('state', 'N/A')} {stop.get('zip_code', 'N/A')}")
            output.append(f"  Appointment:   {stop.get('appointment', 'N/A')}")
            if stop.get('po_numbers'):
                po_str = ', '.join(str(p) for p in stop.get('po_numbers', []))
                output.append(f"  PO Numbers:    {po_str}")
            if stop.get('notes'):
                output.append(f"  Notes:         {stop.get('notes')}")
        
        # Billing
        output.append("\n╔" + "="*78 + "╗")
        output.append("║ BILLING" + " "*69 + "║")
        output.append("╚" + "="*78 + "╝")
        output.append(f"Standard Pay:   {data_dict.get('invoice_email_standard_pay', 'UNKNOWN')}")
        output.append(f"Quick Pay:      {data_dict.get('invoice_email_quick_pay', 'UNKNOWN')}")
    
    output.append("\n" + "="*80 + "\n")
    return "\n".join(output)


SAMPLE_PARSED_DATA_PASS = ParsedRateConData(
    classification="PASS",
    classification_reason="",
    reference_number="RC-12345",
    bol_number="BOL-67890",
    customer_name="Acme Shipping Co",
    trailer_type="53' Dry Van",
    stops=[
        ParsedStop(
            stop_type="PICKUP",
            street_address="123 Warehouse Blvd",
            city="Los Angeles",
            state="CA",
            zip_code="90001",
            appointment="02/25/2026 08:00",
            po_numbers=["PO-111"],
            notes="Dock door #5",
        ),
        ParsedStop(
            stop_type="DELIVERY",
            street_address="456 Distribution Way",
            city="Portland",
            state="OR",
            zip_code="97201",
            appointment="02/27/2026 14:00",
            po_numbers=[],
            notes="",
        ),
    ],
    invoice_email_standard_pay="billing@acme.com",
    invoice_email_quick_pay="quickpay@acme.com",
)

SAMPLE_PARSED_DATA_FAIL = ParsedRateConData(
    classification="FAIL",
    classification_reason="This document appears to be an invoice, not a rate confirmation. It lacks pickup/delivery information and carrier details.",
)


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

    def test_classification_fields(self):
        doc = RateConDocumentFactory(
            organization=self.organization,
            classification_passed=True,
            classification_reason="Looks good",
        )
        doc.refresh_from_db()
        self.assertTrue(doc.classification_passed)
        self.assertEqual(doc.classification_reason, "Looks good")

    def test_str_representation(self):
        doc = RateConDocumentFactory(organization=self.organization)
        self.assertIn("RateConDocument", str(doc))


# ============================================================================
# Text Extraction Tests
# ============================================================================

@override_settings(DEBUG=False)
class TextExtractionTests(TestCase):
    """Tests for PDF text extraction via LiteParse CLI."""

    def test_extract_text_from_pdf(self):
        buffer = _create_pdf_buffer("Hello rate confirmation world")
        text = extract_text_from_pdf(buffer)
        self.assertIn("Hello rate confirmation world", text)

    def test_extract_text_from_empty_pdf(self):
        buffer = _create_empty_pdf_buffer()
        text = extract_text_from_pdf(buffer)
        self.assertEqual(text.strip(), "")

    def test_extract_text_multipage(self):
        buffer = _create_multipage_pdf_buffer(["Page 1 content", "Page 2 content"])
        text = extract_text_from_pdf(buffer)
        self.assertIn("Page 1 content", text)
        self.assertIn("Page 2 content", text)


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
    @patch('machtms.agents.members.ratecon_load_creator.ratecon_load_creator')
    def test_process_document_pass(self, mock_load_creator, mock_agent, mock_download):
        doc = self._create_pending_doc()

        # Mock S3 download
        pdf_buffer = _create_pdf_buffer("Rate Confirmation RC-12345")
        mock_download.return_value = pdf_buffer

        # Mock agent response (structured output)
        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_PASS
        mock_agent.run.return_value = mock_response

        mock_load_creator.run.return_value = MagicMock(content="Load created")

        process_single_document(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.PARSED)
        self.assertIsNotNone(doc.processed_at)
        self.assertTrue(doc.classification_passed)

    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    @patch('machtms.agents.members.rate_con_processor.rate_con_processor')
    def test_process_document_fail_classification(self, mock_agent, mock_download):
        doc = self._create_pending_doc()

        pdf_buffer = _create_pdf_buffer("This is an invoice")
        mock_download.return_value = pdf_buffer

        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_FAIL
        mock_agent.run.return_value = mock_response

        process_single_document(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.MISCLASSIFIED)
        self.assertFalse(doc.classification_passed)

    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    def test_process_document_empty_pdf(self, mock_download):
        doc = self._create_pending_doc()

        # Empty PDF
        mock_download.return_value = _create_empty_pdf_buffer()

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
    @patch('machtms.agents.members.ratecon_load_creator.ratecon_load_creator')
    def test_session_status_updates_after_processing(self, mock_load_creator, mock_agent, mock_download):
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
        mock_response.content = SAMPLE_PARSED_DATA_PASS
        mock_agent.run.return_value = mock_response

        mock_load_creator.run.return_value = MagicMock(content="Load created")

        process_single_document(doc.pk)

        session.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.COMPLETED)


# ============================================================================
# Process Document Mode Tests (raw text vs. PDF URL)
# ============================================================================

@override_settings(DEBUG=False)
class ProcessDocumentModeTests(TestCase):
    """Tests for process_single_document with use_raw_text flag."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Org Mode",
            phone="555-000-0000",
            email="mode@org.com",
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
    @patch('machtms.agents.members.ratecon_load_creator.ratecon_load_creator')
    def test_raw_text_path_calls_agent_with_string(self, mock_load_creator, mock_agent, mock_download):
        """use_raw_text=True calls agent.run(text) without files kwarg."""
        doc = self._create_pending_doc()

        pdf_buffer = _create_pdf_buffer("Rate Confirmation RC-12345")
        mock_download.return_value = pdf_buffer

        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_PASS
        mock_agent.run.return_value = mock_response
        mock_load_creator.run.return_value = MagicMock(content="Load created")

        process_single_document(doc.pk, use_raw_text=True)

        # Agent should be called with text, NOT with files
        mock_agent.run.assert_called_once()
        call_kwargs = mock_agent.run.call_args
        self.assertNotIn('files', call_kwargs.kwargs)
        # First positional arg should be a text string
        self.assertIsInstance(call_kwargs.args[0], str)
        self.assertIn("Rate Confirmation", call_kwargs.args[0])

    @patch('machtms.backend.RateConParser.tasks.send_pdf_url_to_agent')
    @patch('machtms.agents.members.rate_con_processor.rate_con_processor')
    @patch('machtms.agents.members.ratecon_load_creator.ratecon_load_creator')
    def test_pdf_url_path_calls_send_pdf_url_to_agent(self, mock_load_creator, mock_agent, mock_send_pdf):
        """use_raw_text=False calls send_pdf_url_to_agent instead of downloading."""
        doc = self._create_pending_doc()

        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_PASS
        mock_send_pdf.return_value = mock_response
        mock_load_creator.run.return_value = MagicMock(content="Load created")

        process_single_document(doc.pk, use_raw_text=False)

        # send_pdf_url_to_agent should be called
        mock_send_pdf.assert_called_once()
        call_kwargs = mock_send_pdf.call_args
        self.assertEqual(call_kwargs.kwargs['s3_key'], doc.s3_key)

    @patch('machtms.backend.RateConParser.tasks.send_pdf_url_to_agent')
    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    @patch('machtms.agents.members.ratecon_load_creator.ratecon_load_creator')
    def test_pdf_url_path_does_not_download_from_s3(self, mock_load_creator, mock_download, mock_send_pdf):
        """use_raw_text=False should NOT call download_from_buffer."""
        doc = self._create_pending_doc()

        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_PASS
        mock_send_pdf.return_value = mock_response
        mock_load_creator.run.return_value = MagicMock(content="Load created")

        process_single_document(doc.pk, use_raw_text=False)

        mock_download.assert_not_called()

    @patch('machtms.backend.RateConParser.tasks.send_pdf_url_to_agent')
    @patch('machtms.agents.members.ratecon_load_creator.ratecon_load_creator')
    def test_pdf_url_path_pass_stores_classification(self, mock_load_creator, mock_send_pdf):
        """PASS classification via PDF URL path stores classification on document."""
        doc = self._create_pending_doc()

        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_PASS
        mock_send_pdf.return_value = mock_response
        mock_load_creator.run.return_value = MagicMock(content="Load created")

        process_single_document(doc.pk, use_raw_text=False)

        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.PARSED)
        self.assertTrue(doc.classification_passed)

    @patch('machtms.backend.RateConParser.tasks.send_pdf_url_to_agent')
    def test_pdf_url_path_fail_sets_misclassified(self, mock_send_pdf):
        """FAIL classification via PDF URL path sets MISCLASSIFIED status."""
        doc = self._create_pending_doc()

        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_FAIL
        mock_send_pdf.return_value = mock_response

        process_single_document(doc.pk, use_raw_text=False)

        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.MISCLASSIFIED)
        self.assertFalse(doc.classification_passed)

    @patch('machtms.core.utils.s3_utils.generate_presigned_url')
    def test_send_pdf_url_to_agent_generates_presigned_url(self, mock_presigned):
        """Unit test send_pdf_url_to_agent generates a presigned URL and calls agent.run with File."""
        mock_presigned.return_value = "https://s3.example.com/test-key?signed=1"

        mock_agent = MagicMock()
        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_PASS
        mock_agent.run.return_value = mock_response

        result = send_pdf_url_to_agent(
            s3_key="test-key.pdf",
            agent=mock_agent,
            session_id="test-session",
            dependencies={"organization": self.organization},
        )

        mock_presigned.assert_called_once_with(
            'get_object',
            bucket_name=settings.AWS_RATECON_PARSE_BUCKET,
            object_key="test-key.pdf",
            expires=300,
        )
        mock_agent.run.assert_called_once()
        call_kwargs = mock_agent.run.call_args
        self.assertIn('files', call_kwargs.kwargs)
        self.assertEqual(len(call_kwargs.kwargs['files']), 1)
        self.assertEqual(result, mock_response)


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

        parsed_data = response.content  # ParsedRateConData instance
        self.assertIn(parsed_data.classification, ['PASS', 'FAIL'],
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

        parsed_data = response.content  # ParsedRateConData instance
        self.assertEqual(parsed_data.classification, 'FAIL')


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
        """Verify LiteParse can extract text from the real PDFs."""
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

            parsed_data = response.content  # ParsedRateConData instance
            print(f"\n--- Agent Structured Output ---")
            print(parsed_data.model_dump_json(indent=2))

            print(f"\n--- Parsed Result ---")
            print(f"Classification: {parsed_data.classification}")
            if parsed_data.classification_reason:
                print(f"Reason: {parsed_data.classification_reason}")

            if parsed_data.classification == 'PASS':
                print(f"Reference: {parsed_data.reference_number}")
                print(f"Customer: {parsed_data.customer_name}")
                print(f"\nStops ({len(parsed_data.stops)}):")
                for i, stop in enumerate(parsed_data.stops, 1):
                    print(f"  Stop {i}: {stop.stop_type} @ {stop.street_address}, {stop.city}, {stop.state} {stop.zip_code}")

            # Basic assertions
            self.assertIn(parsed_data.classification, ['PASS', 'FAIL'])
            if parsed_data.classification == 'PASS':
                self.assertTrue(
                    len(parsed_data.stops) > 0,
                    f"Expected stops for {filename}"
                )

    def test_full_pipeline_with_real_pdf(self):
        """Test the complete pipeline: extract -> agent -> structured output -> create record."""
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

        # Run agent (returns ParsedRateConData via output_schema)
        response = rate_con_processor.run(
            text,
            session_id=str(uuid.uuid4()),
        )
        parsed_data = response.content  # ParsedRateConData instance

        # Store classification on the document
        doc.classification_passed = (parsed_data.classification == 'PASS')
        doc.classification_reason = parsed_data.classification_reason

        # Update document status
        if parsed_data.classification == 'PASS':
            doc.status = DocumentStatus.PARSED
        else:
            doc.status = DocumentStatus.MISCLASSIFIED
        doc.processed_at = timezone.now()
        doc.save()

        # Verify
        doc.refresh_from_db()
        self.assertIn(doc.status, [DocumentStatus.PARSED, DocumentStatus.MISCLASSIFIED])
        self.assertIsNotNone(doc.classification_passed)

        print(f"\n--- Full Pipeline Result for {filename} ---")
        print(f"Document Status: {doc.status}")
        print(f"Classification: {'PASS' if doc.classification_passed else 'FAIL'}")


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
        parsed_data = parse_response.content  # ParsedRateConData instance
        print(f"\n--- rate_con_processor output ---")
        print(parsed_data.model_dump_json(indent=2))

        self.assertEqual(parsed_data.classification, 'PASS',
                         f"Expected PASS classification for {filename}")

        # Step 3: Feed the parsed output to ratecon_load_creator
        loads_before = Load.objects.filter(organization=self.organization).count()

        creator_prompt = (
            f"Create a load from this parsed rate confirmation data (JSON):\n\n"
            f"{parsed_data.model_dump_json(indent=2)}"
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


# ============================================================================
# E2E Tests for raw text vs. PDF URL mode (requires OPENAI_API_KEY + test_documents/)
# ============================================================================

@skipUnless(
    os.environ.get('OPENAI_API_KEY') and _has_test_documents(),
    "OPENAI_API_KEY not set or test_documents/ missing"
)
@override_settings(DEBUG=False)
class ProcessSingleDocumentModeE2ETests(TestCase):
    """E2E tests comparing use_raw_text=True vs. use_raw_text=False.

    Requires:
    - OPENAI_API_KEY environment variable
    - machtms/test_documents/ directory with at least one PDF
    """

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Mode E2E Org",
            phone="555-000-0000",
            email="mode-e2e@org.com",
        )

    def _get_first_pdf_path(self):
        return os.path.join(
            TEST_DOCUMENTS_DIR,
            sorted(f for f in os.listdir(TEST_DOCUMENTS_DIR) if f.endswith('.pdf'))[0],
        )

    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    def test_use_raw_text_true_with_real_pdf(self, mock_download):
        """use_raw_text=True with a real PDF: mocked S3 download, real agent + load creation."""
        import time
        from machtms.agents.members.rate_con_processor import rate_con_processor

        test_start_time = time.time()

        pdf_path = self._get_first_pdf_path()
        filename = os.path.basename(pdf_path)

        # Extract text from PDF for later display
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        pdf_buffer = BytesIO(pdf_content)
        pdf_text = extract_text_from_pdf(BytesIO(pdf_content))

        mock_download.return_value = BytesIO(pdf_content)

        session = ParsingSessionFactory(organization=self.organization)
        doc = RateConDocumentFactory(
            session=session,
            organization=self.organization,
            original_filename=filename,
            status=DocumentStatus.PENDING,
        )

        # Time the actual document processing
        process_start_time = time.time()
        process_single_document(doc.pk, use_raw_text=True)
        process_end_time = time.time()
        process_duration = process_end_time - process_start_time

        doc.refresh_from_db()
        
        # Also run the agent directly to get prettified output
        agent_start = time.time()
        agent_response = rate_con_processor.run(
            pdf_text,
            session_id=str(uuid.uuid4()),
        )
        agent_end = time.time()
        agent_duration = agent_end - agent_start
        
        parsed_data = agent_response.content
        
        # Print timing and results
        print(f"\n{'='*80}")
        print(f"TEST: use_raw_text=True with Real PDF")
        print(f"{'='*80}")
        print(f"Document: {filename}")
        print(f"Status: {doc.status}")
        print(f"Classification: {'PASS' if doc.classification_passed else 'FAIL'}")
        print(f"\nTiming:")
        print(f"  Document Processing: {process_duration:.3f}s")
        print(f"  Agent Processing:    {agent_duration:.3f}s")
        
        test_end_time = time.time()
        total_duration = test_end_time - test_start_time
        print(f"  Total Test Duration: {total_duration:.3f}s")
        
        # Print prettified parsed data
        print(_prettify_parsed_data(parsed_data))

        # Print the actual Load created in the DB
        if doc.status == DocumentStatus.PARSED:
            from machtms.backend.loads.models import Load
            from machtms.backend.addresses.models import Address
            load = Load.objects.filter(ratecondocument=doc).first()
            if load:
                print("\n" + "="*80)
                print("LOAD CREATED IN DATABASE")
                print("="*80)
                print(f"  Load ID:          {load.pk}")
                print(f"  Reference #:      {load.reference_number}")
                print(f"  BOL #:            {load.bol_number}")
                print(f"  Trailer Type:     {load.trailer_type}")
                print(f"  Status:           {load.status}")
                print(f"  Billing Status:   {load.billing_status}")
                if load.customer:
                    print(f"  Customer:         {load.customer.customer_name}")
                for leg in load.legs.all():
                    print(f"\n  Leg {leg.pk}:")
                    for stop in leg.stops.select_related('address').all():
                        addr = stop.address
                        print(f"    Stop {stop.stop_number} ({stop.action}):")
                        if addr.place_name:
                            print(f"      Location:     {addr.place_name}")
                        print(f"      Address:      {addr.street}")
                        print(f"                    {addr.city}, {addr.state} {addr.zip_code}")
                        print(f"      Appointment:  {stop.start_range}")
                        if stop.po_numbers:
                            print(f"      PO Numbers:   {stop.po_numbers}")
                        if stop.driver_notes:
                            print(f"      Driver Notes: {stop.driver_notes}")
                print("\n" + "="*80)
            else:
                print("\n[WARNING] Status is PARSED but no Load found linked to this document.")

        self.assertIn(doc.status, [DocumentStatus.PARSED, DocumentStatus.MISCLASSIFIED])
        self.assertIsNotNone(doc.classification_passed)

    @patch('machtms.core.utils.s3_utils.generate_presigned_url')
    def test_use_raw_text_false_with_real_pdf(self, mock_presigned):
        """use_raw_text=False with a real PDF: local HTTP server serves the PDF to the agent."""
        import time
        import threading
        import http.server
        import functools
        from machtms.agents.members.rate_con_processor import rate_con_processor

        test_start_time = time.time()

        pdf_path = self._get_first_pdf_path()
        filename = os.path.basename(pdf_path)

        # Serve test_documents/ over a local HTTP server so the agent can fetch the PDF
        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler,
            directory=TEST_DOCUMENTS_DIR,
        )
        server = http.server.HTTPServer(('127.0.0.1', 0), handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        local_url = f"http://127.0.0.1:{port}/{filename}"
        mock_presigned.return_value = local_url

        session = ParsingSessionFactory(organization=self.organization)
        doc = RateConDocumentFactory(
            session=session,
            organization=self.organization,
            original_filename=filename,
            status=DocumentStatus.PENDING,
        )

        # Time the document processing
        process_start_time = time.time()
        process_single_document(doc.pk, use_raw_text=False)
        process_end_time = time.time()
        process_duration = process_end_time - process_start_time

        doc.refresh_from_db()

        # Also run the agent directly to get prettified output
        from agno.media import File as AgnoFile
        agent_start = time.time()
        agent_response = rate_con_processor.run(
            "Process this rate confirmation document.",
            files=[AgnoFile(url=local_url)],
            session_id=str(uuid.uuid4()),
        )
        agent_end = time.time()
        agent_duration = agent_end - agent_start

        server.shutdown()

        parsed_data = agent_response.content

        # Print timing and results
        print(f"\n{'='*80}")
        print(f"TEST: use_raw_text=False with Real PDF (no LiteParse)")
        print(f"{'='*80}")
        print(f"Document: {filename}")
        print(f"Status: {doc.status}")
        print(f"Classification: {'PASS' if doc.classification_passed else 'FAIL'}")
        print(f"\nTiming:")
        print(f"  Document Processing: {process_duration:.3f}s")
        print(f"  Agent Processing:    {agent_duration:.3f}s")

        test_end_time = time.time()
        total_duration = test_end_time - test_start_time
        print(f"  Total Test Duration: {total_duration:.3f}s")

        # Print prettified parsed data
        print(_prettify_parsed_data(parsed_data))

        self.assertIn(doc.status, [DocumentStatus.PARSED, DocumentStatus.MISCLASSIFIED])
        self.assertIsNotNone(doc.classification_passed)
