"""
Test suite for Rate Confirmation Agent Pipeline Enhancements.

This module contains tests for:
1. Pydantic model updates (ParsedStop, ParsedRateConData, RateConLoadPayload)
2. StopHistoryToolkit get_action_code_frequency method
3. Agent configuration (rate_con_processor, ratecon_load_creator)
4. DocumentParsingToolkit (update_document_status, assign_load_to_parsed_ratecon)
5. LoadToolkit metadata stripping (create_load_from_parsed)
6. Celery task integration (dependencies passing)
"""
import json
import uuid
from io import BytesIO
from unittest.mock import patch, MagicMock

import pymupdf
from agno.run.base import RunContext
from django.test import TestCase, override_settings
from django.utils import timezone

from machtms.agents.models.ratecon_payload import (
    ParsedStop,
    ParsedRateConData,
    RateConLoadPayload,
)
from machtms.agents.toolkit.document_parsing import DocumentParsingToolkit
from machtms.agents.toolkit.loads import LoadToolkit
from machtms.agents.toolkit.stops import StopHistoryToolkit
from machtms.backend.auth.models import Organization
from machtms.backend.RateConParser.models import (
    DocumentStatus,
    ParsedRateCon,
)
from machtms.backend.RateConParser.tasks import process_single_document
from machtms.core.factories import (
    AddressFactory,
    LegFactory,
    LoadFactory,
    StopFactory,
    ParsingSessionFactory,
    RateConDocumentFactory,
    ParsedRateConFactory,
)


def _make_run_context(organization, celery_task_id="", ratecon_id=None):
    """Create a mock RunContext with the given organization in dependencies."""
    return RunContext(
        run_id="test-run",
        session_id="test-session",
        dependencies={
            "organization": organization,
            "celery_task_id": celery_task_id,
            "ratecon_id": ratecon_id,
        },
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
    classification_reason="This document appears to be an invoice, not a rate confirmation.",
)


# ============================================================================
# ParsedStop Model Tests
# ============================================================================

@override_settings(DEBUG=False)
class ParsedStopModelTests(TestCase):
    """Tests for the updated ParsedStop Pydantic model."""

    def test_street_address_field_exists(self):
        stop = ParsedStop(stop_type="PICKUP", street_address="123 Main St")
        self.assertEqual(stop.street_address, "123 Main St")

    def test_po_numbers_is_list(self):
        stop = ParsedStop(stop_type="PICKUP", po_numbers=["PO-1", "PO-2"])
        self.assertIsInstance(stop.po_numbers, list)
        self.assertEqual(stop.po_numbers, ["PO-1", "PO-2"])

    def test_po_numbers_default_empty_list(self):
        stop = ParsedStop(stop_type="PICKUP")
        self.assertEqual(stop.po_numbers, [])

    def test_stop_type_has_description(self):
        field_info = ParsedStop.model_fields['stop_type']
        self.assertIsNotNone(field_info.description)
        self.assertIn("Live Load", field_info.description)
        self.assertIn("Live Unload", field_info.description)

    def test_no_old_address_field(self):
        self.assertNotIn('address', ParsedStop.model_fields)


# ============================================================================
# ParsedRateConData Model Tests
# ============================================================================

@override_settings(DEBUG=False)
class ParsedRateConDataModelTests(TestCase):
    """Tests for the updated ParsedRateConData Pydantic model."""

    def test_bol_number_has_description(self):
        field_info = ParsedRateConData.model_fields['bol_number']
        self.assertIsNotNone(field_info.description)
        self.assertIn("PU#", field_info.description)
        self.assertIn("BOL#", field_info.description)

    def test_invoice_email_standard_pay_default(self):
        data = ParsedRateConData()
        self.assertEqual(data.invoice_email_standard_pay, "UNKNOWN")

    def test_invoice_email_quick_pay_default(self):
        data = ParsedRateConData()
        self.assertEqual(data.invoice_email_quick_pay, "UNKNOWN")

    def test_old_invoice_email_removed(self):
        self.assertNotIn('invoice_email', ParsedRateConData.model_fields)

    def test_celery_task_id_default_empty(self):
        data = ParsedRateConData()
        self.assertEqual(data.celery_task_id, "")

    def test_ratecon_document_id_default_none(self):
        data = ParsedRateConData()
        self.assertIsNone(data.ratecon_document_id)

    def test_full_model_construction(self):
        data = ParsedRateConData(
            classification="PASS",
            reference_number="RC-123",
            bol_number="BOL-456",
            customer_name="Test Corp",
            trailer_type="53' Dry Van",
            stops=[
                ParsedStop(
                    stop_type="PICKUP",
                    street_address="123 Main St",
                    city="LA",
                    state="CA",
                    zip_code="90001",
                    po_numbers=["PO-1"],
                ),
            ],
            invoice_email_standard_pay="billing@test.com",
            invoice_email_quick_pay="qp@test.com",
            celery_task_id="abc-123",
            ratecon_document_id=42,
        )
        self.assertEqual(data.classification, "PASS")
        self.assertEqual(data.celery_task_id, "abc-123")
        self.assertEqual(data.ratecon_document_id, 42)
        self.assertEqual(len(data.stops), 1)
        self.assertEqual(data.stops[0].street_address, "123 Main St")


# ============================================================================
# RateConLoadPayload Model Tests
# ============================================================================

@override_settings(DEBUG=False)
class RateConLoadPayloadModelTests(TestCase):
    """Tests for the updated RateConLoadPayload Pydantic model."""

    def test_celery_task_id_present(self):
        payload = RateConLoadPayload(celery_task_id="task-123")
        self.assertEqual(payload.celery_task_id, "task-123")

    def test_ratecon_document_id_present(self):
        payload = RateConLoadPayload(ratecon_document_id=99)
        self.assertEqual(payload.ratecon_document_id, 99)

    def test_model_dump_excludes_metadata(self):
        payload = RateConLoadPayload(
            reference_number="REF-1",
            celery_task_id="task-1",
            ratecon_document_id=5,
        )
        dumped = payload.model_dump(exclude={'celery_task_id', 'ratecon_document_id'})
        self.assertNotIn('celery_task_id', dumped)
        self.assertNotIn('ratecon_document_id', dumped)
        self.assertEqual(dumped['reference_number'], "REF-1")


# ============================================================================
# StopHistoryToolkit Tests (get_action_code_frequency)
# ============================================================================

@override_settings(DEBUG=False)
class StopHistoryToolkitRefactoredTests(TestCase):
    """Tests for the new get_action_code_frequency method."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-000-0000",
            email="test@org.com",
        )
        cls.other_org = Organization.objects.create(
            company_name="Other Org",
            phone="555-000-0001",
            email="other@org.com",
        )
        cls.toolkit = StopHistoryToolkit()

    def test_get_action_code_frequency_with_history(self):
        address = AddressFactory(organization=self.organization)
        load = LoadFactory(organization=self.organization)
        leg = LegFactory(load=load, organization=self.organization)

        # Create stops with mixed actions
        StopFactory(
            leg=leg, address=address, action='LL',
            stop_number=1, organization=self.organization,
        )
        StopFactory(
            leg=leg, address=address, action='LL',
            stop_number=2, organization=self.organization,
        )
        StopFactory(
            leg=leg, address=address, action='HL',
            stop_number=3, organization=self.organization,
        )

        ctx = _make_run_context(self.organization)
        result = json.loads(self.toolkit.get_action_code_frequency(ctx, address.pk))

        self.assertTrue(result['has_history'])
        self.assertEqual(result['address_id'], address.pk)
        self.assertEqual(result['suggested_action'], 'LL')
        self.assertEqual(result['action_counts']['LL'], 2)
        self.assertEqual(result['action_counts']['HL'], 1)

    def test_get_action_code_frequency_no_history(self):
        address = AddressFactory(organization=self.organization)
        ctx = _make_run_context(self.organization)
        result = json.loads(self.toolkit.get_action_code_frequency(ctx, address.pk))

        self.assertFalse(result['has_history'])
        self.assertIsNone(result['suggested_action'])
        self.assertEqual(result['action_counts'], {})

    def test_get_action_code_frequency_single_action(self):
        address = AddressFactory(organization=self.organization)
        load = LoadFactory(organization=self.organization)
        leg = LegFactory(load=load, organization=self.organization)

        StopFactory(
            leg=leg, address=address, action='LU',
            stop_number=1, organization=self.organization,
        )

        ctx = _make_run_context(self.organization)
        result = json.loads(self.toolkit.get_action_code_frequency(ctx, address.pk))

        self.assertTrue(result['has_history'])
        self.assertEqual(result['suggested_action'], 'LU')
        self.assertEqual(result['action_counts'], {'LU': 1})

    def test_get_action_code_frequency_org_isolation(self):
        address = AddressFactory(organization=self.organization)

        # Create stops under the other org at the same address
        other_load = LoadFactory(organization=self.other_org)
        other_leg = LegFactory(load=other_load, organization=self.other_org)
        StopFactory(
            leg=other_leg, address=address, action='HL',
            stop_number=1, organization=self.other_org,
        )

        # Query from the first org — should see no history
        ctx = _make_run_context(self.organization)
        result = json.loads(self.toolkit.get_action_code_frequency(ctx, address.pk))

        self.assertFalse(result['has_history'])
        self.assertIsNone(result['suggested_action'])


# ============================================================================
# RateConProcessor Agent Config Tests
# ============================================================================

@override_settings(DEBUG=False)
class RateConProcessorConfigTests(TestCase):
    """Tests for rate_con_processor agent configuration."""

    def setUp(self):
        from machtms.agents.members.rate_con_processor import rate_con_processor
        self.agent = rate_con_processor

    def test_has_output_schema(self):
        self.assertEqual(self.agent.output_schema, ParsedRateConData)

    def test_instructions_mention_classification(self):
        instructions = "\n".join(self.agent.instructions)
        self.assertIn("CLASSIFICATION", instructions)

    def test_instructions_mention_extraction(self):
        instructions = "\n".join(self.agent.instructions)
        self.assertIn("EXTRACTION", instructions)


# ============================================================================
# RateConLoadCreator Agent Config Tests
# ============================================================================

@override_settings(DEBUG=False)
class RateConLoadCreatorConfigTests(TestCase):
    """Tests for ratecon_load_creator agent configuration."""

    def setUp(self):
        from machtms.agents.members.ratecon_load_creator import ratecon_load_creator
        self.agent = ratecon_load_creator
        self.instructions = "\n".join(
            line for line in self.agent.instructions if isinstance(line, str)
        )

    def test_has_stop_history_toolkit(self):
        toolkit_types = [type(t).__name__ for t in self.agent.tools]
        self.assertIn('StopHistoryToolkit', toolkit_types)

    def test_has_document_parsing_toolkit(self):
        toolkit_types = [type(t).__name__ for t in self.agent.tools]
        self.assertIn('DocumentParsingToolkit', toolkit_types)

    def test_instructions_mention_get_action_code_frequency(self):
        self.assertIn("get_action_code_frequency()", self.instructions)

    def test_instructions_mention_assign_load(self):
        self.assertIn("assign_load_to_parsed_ratecon()", self.instructions)

    def test_instructions_no_longer_mention_old_update_method(self):
        self.assertNotIn("update_ratecon_document_status()", self.instructions)


# ============================================================================
# DocumentParsingToolkit Tests
# ============================================================================

@override_settings(DEBUG=False)
class DocumentParsingToolkitTests(TestCase):
    """Tests for DocumentParsingToolkit methods."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-000-0000",
            email="test@org.com",
        )
        cls.toolkit = DocumentParsingToolkit()

    # --- update_document_status ---

    def test_update_document_status_success(self):
        session = ParsingSessionFactory(organization=self.organization)
        doc = RateConDocumentFactory(
            session=session,
            organization=self.organization,
            status=DocumentStatus.PENDING,
        )
        ctx = _make_run_context(self.organization, ratecon_id=doc.pk)
        result = self.toolkit.update_document_status(ctx, DocumentStatus.PROCESSING)

        self.assertIn("Successfully updated", result)
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.PROCESSING)

    def test_update_document_status_invalid_status(self):
        session = ParsingSessionFactory(organization=self.organization)
        doc = RateConDocumentFactory(
            session=session,
            organization=self.organization,
        )
        ctx = _make_run_context(self.organization, ratecon_id=doc.pk)
        result = self.toolkit.update_document_status(ctx, "bogus_status")

        self.assertIn("Error", result)
        self.assertIn("Invalid status", result)

    def test_update_document_status_not_found(self):
        ctx = _make_run_context(self.organization, ratecon_id=99999)
        result = self.toolkit.update_document_status(ctx, DocumentStatus.PARSED)

        self.assertIn("Error", result)
        self.assertIn("not found", result)

    def test_update_document_status_missing_dependency(self):
        ctx = _make_run_context(self.organization)  # ratecon_id defaults to None
        result = self.toolkit.update_document_status(ctx, DocumentStatus.PARSED)

        self.assertIn("Error", result)
        self.assertIn("ratecon_id not found", result)

    # --- assign_load_to_parsed_ratecon ---

    def test_assign_load_to_parsed_ratecon_success(self):
        session = ParsingSessionFactory(organization=self.organization)
        doc = RateConDocumentFactory(
            session=session,
            organization=self.organization,
            status=DocumentStatus.PARSED,
        )
        parsed = ParsedRateConFactory(
            document=doc,
            organization=self.organization,
        )
        load = LoadFactory(organization=self.organization)

        ctx = _make_run_context(self.organization, ratecon_id=doc.pk)
        result = self.toolkit.assign_load_to_parsed_ratecon(ctx, load.pk)

        self.assertIn("Successfully linked", result)
        parsed.refresh_from_db()
        self.assertEqual(parsed.load_id, load.pk)

    def test_assign_load_to_parsed_ratecon_not_found(self):
        ctx = _make_run_context(self.organization, ratecon_id=99999)
        result = self.toolkit.assign_load_to_parsed_ratecon(ctx, 1)

        self.assertIn("Error", result)
        self.assertIn("No ParsedRateCon found", result)

    def test_assign_load_to_parsed_ratecon_missing_dependency(self):
        ctx = _make_run_context(self.organization)  # ratecon_id defaults to None
        result = self.toolkit.assign_load_to_parsed_ratecon(ctx, 1)

        self.assertIn("Error", result)
        self.assertIn("ratecon_id not found", result)


# ============================================================================
# LoadToolkit Metadata Stripping Tests
# ============================================================================

@override_settings(DEBUG=False)
class LoadToolkitMetadataStrippingTests(TestCase):
    """Tests for LoadToolkit create_load_from_parsed metadata stripping."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-000-0000",
            email="test@org.com",
        )
        cls.toolkit = LoadToolkit()

    def test_create_load_from_parsed_strips_metadata(self):
        """Verify that celery_task_id and ratecon_document_id are stripped before serializer."""
        ctx = _make_run_context(self.organization)

        payload = {
            "customer": None,
            "reference_number": "REF-STRIP-TEST",
            "bol_number": "BOL-1",
            "trailer_type": "",
            "status": "pending",
            "billing_status": "pending_delivery",
            "celery_task_id": "task-xyz",
            "ratecon_document_id": 42,
            "legs": [],
        }

        with patch.object(self.toolkit, 'create_load') as mock_create:
            mock_create.return_value = "Load created!"
            result = self.toolkit.create_load_from_parsed(ctx, json.dumps(payload))

            # Verify create_load was called with JSON that excludes metadata
            call_args = mock_create.call_args
            passed_json = call_args[0][1]
            parsed_back = json.loads(passed_json)
            self.assertNotIn('celery_task_id', parsed_back)
            self.assertNotIn('ratecon_document_id', parsed_back)
            self.assertEqual(parsed_back['reference_number'], "REF-STRIP-TEST")


# ============================================================================
# Celery Task Integration Tests
# ============================================================================

@override_settings(DEBUG=False)
class CeleryTaskIntegrationTests(TestCase):
    """Tests for Celery task integration with ratecon_load_creator."""

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
    def test_process_document_pass_triggers_load_creator(
        self, mock_load_creator, mock_processor, mock_download
    ):
        doc = self._create_pending_doc()
        mock_download.return_value = _create_pdf_buffer("Rate Con")

        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_PASS
        mock_processor.run.return_value = mock_response

        mock_load_creator.run.return_value = MagicMock(content="Load created")

        process_single_document(doc.pk)

        mock_load_creator.run.assert_called_once()
        call_kwargs = mock_load_creator.run.call_args[1]
        self.assertEqual(call_kwargs['dependencies']['ratecon_id'], doc.pk)
        self.assertIn('celery_task_id', call_kwargs['dependencies'])

    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    @patch('machtms.agents.members.rate_con_processor.rate_con_processor')
    @patch('machtms.agents.members.ratecon_load_creator.ratecon_load_creator')
    def test_process_document_fail_does_not_trigger_load_creator(
        self, mock_load_creator, mock_processor, mock_download
    ):
        doc = self._create_pending_doc()
        mock_download.return_value = _create_pdf_buffer("Invoice")

        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_FAIL
        mock_processor.run.return_value = mock_response

        process_single_document(doc.pk)
        mock_load_creator.run.assert_not_called()

    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    @patch('machtms.agents.members.rate_con_processor.rate_con_processor')
    @patch('machtms.agents.members.ratecon_load_creator.ratecon_load_creator')
    def test_process_document_load_creator_error_does_not_fail_document(
        self, mock_load_creator, mock_processor, mock_download
    ):
        doc = self._create_pending_doc()
        mock_download.return_value = _create_pdf_buffer("Rate Con")

        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_PASS
        mock_processor.run.return_value = mock_response

        mock_load_creator.run.side_effect = Exception("Agent crashed")

        process_single_document(doc.pk)

        doc.refresh_from_db()
        # Document should still be PARSED — load creator failure doesn't affect it
        self.assertEqual(doc.status, DocumentStatus.PARSED)

    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    @patch('machtms.agents.members.rate_con_processor.rate_con_processor')
    @patch('machtms.agents.members.ratecon_load_creator.ratecon_load_creator')
    def test_process_document_passes_metadata_in_dependencies(
        self, mock_load_creator, mock_processor, mock_download
    ):
        doc = self._create_pending_doc()
        doc.celery_task_id = "celery-task-abc"
        doc.save(update_fields=['celery_task_id'])

        mock_download.return_value = _create_pdf_buffer("Rate Con")

        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_PASS
        mock_processor.run.return_value = mock_response

        mock_load_creator.run.return_value = MagicMock(content="Load created")

        process_single_document(doc.pk)

        call_kwargs = mock_load_creator.run.call_args[1]
        deps = call_kwargs['dependencies']
        self.assertEqual(deps['celery_task_id'], "celery-task-abc")
        self.assertEqual(deps['ratecon_id'], doc.pk)

        # Verify metadata is NOT in the prompt text
        prompt = mock_load_creator.run.call_args[0][0]
        self.assertNotIn("Metadata:", prompt)
        self.assertNotIn("celery_task_id:", prompt)
        self.assertNotIn("ratecon_document_id:", prompt)

    @patch('machtms.core.utils.s3_utils.download_from_buffer')
    @patch('machtms.agents.members.rate_con_processor.rate_con_processor')
    def test_process_document_passes_dependencies_to_processor(
        self, mock_processor, mock_download
    ):
        doc = self._create_pending_doc()
        doc.celery_task_id = "celery-task-xyz"
        doc.save(update_fields=['celery_task_id'])

        mock_download.return_value = _create_pdf_buffer("Rate Con")

        mock_response = MagicMock()
        mock_response.content = SAMPLE_PARSED_DATA_FAIL
        mock_processor.run.return_value = mock_response

        process_single_document(doc.pk)

        call_kwargs = mock_processor.run.call_args[1]
        deps = call_kwargs['dependencies']
        self.assertEqual(deps['celery_task_id'], "celery-task-xyz")
        self.assertEqual(deps['ratecon_id'], doc.pk)
