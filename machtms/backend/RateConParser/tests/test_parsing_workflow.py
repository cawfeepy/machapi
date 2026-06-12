"""
Multi-document workflow tests for the RateConParser pipeline.

Tests the full upload-and-parse workflow with multiple PDF documents,
covering both raw_text and PDF mode in sync and async processing modes.

Requires:
- OPENAI_API_KEY environment variable
- AWS_ACCESS_KEY environment variable
- test_documents/ directory with PDF files
"""
import os
import time

import boto3
import requests
from django.conf import settings
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from unittest import skipUnless

from machtms.core.testing import OrganizationAPIClient
from machtms.backend.auth.models import Organization, OrganizationUser, UserProfile
from machtms.backend.RateConParser.models import (
    ParsingSession,
    RateConDocument,
    DocumentStatus,
    SessionStatus,
)


TEST_DOCUMENTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', '..', '..', 'test_documents'
)

HAS_OPENAI = bool(os.environ.get('OPENAI_API_KEY'))
HAS_AWS = bool(os.environ.get('AWS_ACCESS_KEY'))
HAS_TEST_DOCS = os.path.isdir(TEST_DOCUMENTS_DIR)
HAS_CELERY = bool(os.environ.get('USE_CELERY_TESTS'))

TERMINAL_STATUSES = {
    DocumentStatus.PARSED,
    DocumentStatus.MISCLASSIFIED,
    DocumentStatus.FAILED,
}


@skipUnless(
    HAS_OPENAI and HAS_AWS and HAS_TEST_DOCS and HAS_CELERY,
    "Requires --use-celery flag, OPENAI_API_KEY, AWS credentials, and test_documents/ directory"
)
@override_settings(DEBUG=False)
class MultiDocumentWorkflowTests(TransactionTestCase):
    """End-to-end multi-document workflow tests for the RateCon parsing pipeline.

    Each test creates a session, uploads ALL test PDFs, triggers sync
    processing, polls for completion, and verifies that every document
    was parsed with a linked Load.
    """

    def setUp(self):
        self.client = OrganizationAPIClient()
        self.organization = Organization.objects.create(
            company_name="Multi-Doc Workflow Org",
            phone="5559990000",
            email="multi-doc@test.com",
        )
        self.user = OrganizationUser.objects.create_user(
            email="multi-doc-test@example.com",
            password="testpass123",
        )
        self.user_profile = UserProfile.objects.create(
            user=self.user,
            organization=self.organization,
        )
        self.client.force_authenticate_with_org(self.user, self.organization)
        self._uploaded_s3_keys = []

    def tearDown(self):
        """Delete all S3 objects uploaded during the test."""
        if self._uploaded_s3_keys:
            try:
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY,
                    aws_secret_access_key=settings.AWS_SECRET_KEY,
                    region_name=settings.AWS_REGION_NAME,
                )
                bucket = settings.AWS_RATECON_PARSE_BUCKET
                for key in self._uploaded_s3_keys:
                    try:
                        s3_client.delete_object(Bucket=bucket, Key=key)
                    except Exception:
                        pass
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_all_test_pdfs(self):
        """Return a sorted list of (filename, pdf_bytes) for every PDF in
        TEST_DOCUMENTS_DIR."""
        results = []
        for fname in sorted(os.listdir(TEST_DOCUMENTS_DIR)):
            if fname.lower().endswith('.pdf'):
                path = os.path.join(TEST_DOCUMENTS_DIR, fname)
                with open(path, 'rb') as f:
                    results.append((fname, f.read()))
        if not results:
            self.fail("No PDF files found in test_documents/")
        return results

    def _upload_document(self, session_id, filename, pdf_bytes):
        """Upload a single document through the full presigned-URL workflow.

        Returns (document_id, s3_key).
        """
        resp = self.client.post(
            reverse('ratecon-document-upload'),
            data={
                'session_id': session_id,
                'filename': filename,
            },
            format='json',
        )
        self.assertEqual(
            resp.status_code, 201,
            f"Document upload registration failed: {resp.data}",
        )
        document_id = resp.data['document_id']
        s3_key = resp.data['s3_key']
        presigned_url = resp.data['presigned_url']
        self._uploaded_s3_keys.append(s3_key)

        upload_resp = requests.put(
            presigned_url,
            data=pdf_bytes,
            headers={'Content-Type': 'application/pdf'},
        )
        self.assertIn(
            upload_resp.status_code, [200, 204],
            f"S3 presigned PUT failed for {filename} "
            f"({upload_resp.status_code}): {upload_resp.text}",
        )

        resp = self.client.post(
            reverse('ratecon-upload-complete'),
            data={'document_id': document_id},
            format='json',
        )
        self.assertEqual(
            resp.status_code, 200,
            f"Upload complete failed for {filename}: {resp.data}",
        )

        return document_id, s3_key

    def _poll_session_completion(self, session_id, document_ids, max_wait=300):
        """Poll until ALL documents reach a terminal status.

        Returns a dict mapping document_id to the refreshed RateConDocument.
        """
        poll_interval = 3
        elapsed = 0
        remaining = set(document_ids)
        results = {}

        while elapsed < max_wait and remaining:
            time.sleep(poll_interval)
            elapsed += poll_interval

            for doc_id in list(remaining):
                doc = RateConDocument.objects.get(pk=doc_id)
                if doc.status in TERMINAL_STATUSES:
                    results[doc_id] = doc
                    remaining.discard(doc_id)

        for doc_id in remaining:
            results[doc_id] = RateConDocument.objects.get(pk=doc_id)

        return results

    def _print_load_details(self, doc, doc_time=None):
        """Pretty-print load information for a single parsed document."""
        load = doc.load
        print(f"\n  {'='*56}")
        print(f"  Document: {doc.original_filename}")
        if doc_time is not None:
            print(f"  Processing Time: {doc_time:.2f}s")
        print(f"  Status: {doc.status}")

        if load is None:
            print("  Load: (none linked)")
            return

        print(f"  Reference #:  {load.reference_number}")
        print(f"  BOL #:        {load.bol_number}")
        print(f"  Customer:     {load.customer}")
        print(f"  Trailer Type: {load.trailer_type}")
        print(f"  Status:       {load.status}")

        for leg in load.legs.prefetch_related('stops__address').all():
            for stop in leg.stops.select_related('address').order_by('stop_number'):
                addr = stop.address
                print(
                    f"    Stop #{stop.stop_number} "
                    f"[{stop.action} - {stop.get_action_display()}]"
                )
                print(
                    f"      Address:     {addr.street}, "
                    f"{addr.city}, {addr.state} {addr.zip_code}"
                )
                if addr.place_name:
                    print(f"      Place:       {addr.place_name}")
                print(f"      Appointment: {stop.start_range}")
                if stop.po_numbers:
                    print(f"      PO #s:       {stop.po_numbers}")
                if stop.driver_notes:
                    print(f"      Notes:       {stop.driver_notes}")

    def _print_summary_table(self, test_name, use_raw_text, mode,
                             total_time, doc_results):
        """Print a formatted summary table of all document results."""
        print(f"\n{'='*80}")
        print(f"  {test_name}")
        print(f"  Mode: {mode}  |  use_raw_text: {use_raw_text}")
        print(f"{'='*80}")
        header = (
            f"  {'Document':<35} {'Status':<15} "
            f"{'Time':>8} {'Load ID':>10} {'Reference #':<20}"
        )
        print(header)
        print(
            f"  {'-'*35} {'-'*15} "
            f"{'-'*8} {'-'*10} {'-'*20}"
        )

        for row in doc_results:
            time_str = (
                f"{row['time']:.1f}s" if row['time'] is not None else "N/A"
            )
            load_str = str(row['load_id']) if row['load_id'] else "-"
            ref_str = row['reference'] or "-"
            print(
                f"  {row['filename']:<35} {row['status']:<15} "
                f"{time_str:>8} {load_str:>10} {ref_str:<20}"
            )

        print(f"\n  Total Time: {total_time:.2f}s")
        print(f"{'='*80}\n")

    # ------------------------------------------------------------------
    # Core workflow runner
    # ------------------------------------------------------------------

    def _run_multi_document_workflow(self, use_raw_text, mode):
        """Run the complete multi-document workflow and return results.

        Args:
            use_raw_text: True uses raw text extraction, False uses direct
                PDF mode.
            mode: 'sync' or 'async'.

        Returns:
            Tuple of (total_time, doc_results_list) where each result dict
            has keys: filename, document_id, status, time, load_id,
            reference, doc, parsed.
        """
        test_pdfs = self._get_all_test_pdfs()

        # 1. Create session
        resp = self.client.post(
            reverse('ratecon-create-session'),
            data={},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        session_id = resp.data['session_id']

        # 2. Upload all documents
        upload_info = []
        for filename, pdf_bytes in test_pdfs:
            doc_id, s3_key = self._upload_document(
                session_id, filename, pdf_bytes,
            )
            upload_info.append((filename, doc_id, s3_key))

        document_ids = [info[1] for info in upload_info]

        # 3. Trigger processing
        if use_raw_text:
            process_url = reverse(
                'ratecon-process-session',
                kwargs={'session_id': session_id},
            )
        else:
            process_url = reverse(
                'ratecon-process-session-pdf',
                kwargs={'session_id': session_id},
            )

        t_start = time.time()
        resp = self.client.post(
            process_url,
            data={'mode': mode},
            format='json',
        )
        self.assertEqual(
            resp.status_code, 202,
            f"Process trigger failed: {resp.data}",
        )

        # 4. Poll for completion, tracking per-document finish times
        doc_finish_times = {}
        poll_interval = 3
        elapsed = 0
        max_wait = 300
        remaining = set(document_ids)

        while elapsed < max_wait and remaining:
            time.sleep(poll_interval)
            elapsed += poll_interval

            for doc_id in list(remaining):
                doc = RateConDocument.objects.get(pk=doc_id)
                if doc.status in TERMINAL_STATUSES:
                    doc_finish_times[doc_id] = time.time() - t_start
                    remaining.discard(doc_id)

        total_time = time.time() - t_start

        # 5. Collect final results
        doc_results = []
        for filename, doc_id, s3_key in upload_info:
            doc = RateConDocument.objects.select_related('load').get(pk=doc_id)
            doc_time = doc_finish_times.get(doc_id)

            load_id = doc.load_id
            reference = doc.load.reference_number if doc.load else None

            doc_results.append({
                'filename': filename,
                'document_id': doc_id,
                'status': doc.status,
                'time': doc_time,
                'load_id': load_id,
                'reference': reference,
                'doc': doc,
            })

        # 6. Assertions
        for result in doc_results:
            self.assertEqual(
                result['status'],
                DocumentStatus.PARSED,
                f"Expected PARSED for {result['filename']} but got "
                f"{result['status']}. Error: {result['doc'].error_message}",
            )
            self.assertIsNotNone(
                result['doc'].load,
                f"RateConDocument.load should not be null for "
                f"{result['filename']}",
            )

        session = ParsingSession.objects.get(pk=session_id)
        self.assertEqual(
            session.status,
            SessionStatus.COMPLETED,
            f"Expected session COMPLETED but got {session.status}",
        )

        # 7. Print details and summary
        mode_label = "raw_text" if use_raw_text else "pdf"
        test_name = f"Multi-Document Workflow ({mode_label}, {mode})"

        for result in doc_results:
            self._print_load_details(result['doc'], result['time'])

        self._print_summary_table(
            test_name, use_raw_text, mode, total_time, doc_results,
        )

        return total_time, doc_results

    # ------------------------------------------------------------------
    # Test methods
    # ------------------------------------------------------------------

    def test_multi_document_raw_text_sync(self):
        """Full multi-document workflow: use_raw_text=True, mode=sync."""
        total_time, results = self._run_multi_document_workflow(
            use_raw_text=True,
            mode='sync',
        )
        self.assertTrue(
            len(results) >= 2, "Expected at least 2 test documents",
        )

    def test_multi_document_pdf_mode_sync(self):
        """Full multi-document workflow: use_raw_text=False, mode=sync."""
        total_time, results = self._run_multi_document_workflow(
            use_raw_text=False,
            mode='sync',
        )
        self.assertTrue(
            len(results) >= 2, "Expected at least 2 test documents",
        )

    def test_multi_document_raw_text_async(self):
        """Full multi-document workflow: use_raw_text=True, mode=async."""
        total_time, results = self._run_multi_document_workflow(
            use_raw_text=True,
            mode='async',
        )
        self.assertTrue(
            len(results) >= 2, "Expected at least 2 test documents",
        )

    def test_multi_document_pdf_mode_async(self):
        """Full multi-document workflow: use_raw_text=False, mode=async."""
        total_time, results = self._run_multi_document_workflow(
            use_raw_text=False,
            mode='async',
        )
        self.assertTrue(
            len(results) >= 2, "Expected at least 2 test documents",
        )
