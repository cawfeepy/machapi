import os
import time

import boto3
import requests
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from unittest import skipUnless

from django.test import TransactionTestCase
from rest_framework.test import APIClient
from machtms.core.testing import OrganizationAPIClient
from machtms.backend.auth.models import Organization, OrganizationUser, UserProfile
from machtms.backend.RateConParser.models import (
    ParsingSession,
    RateConDocument,
    DocumentStatus,
    SessionStatus,
)


# Path to test PDF files
TEST_DOCUMENTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', '..', '..', 'test_documents'
)

HAS_OPENAI = bool(os.environ.get('OPENAI_API_KEY'))
HAS_AWS = bool(os.environ.get('AWS_ACCESS_KEY'))
HAS_TEST_DOCS = os.path.isdir(TEST_DOCUMENTS_DIR)
HAS_CELERY = bool(os.environ.get('USE_CELERY_TESTS'))


@skipUnless(
    HAS_OPENAI and HAS_AWS and HAS_TEST_DOCS and HAS_CELERY,
    "Requires --use-celery flag, OPENAI_API_KEY, AWS credentials, and test_documents/ directory"
)
class IntegratedRateConParserTest(TransactionTestCase):
    """Integration test that acts as the frontend for the RateCon parsing pipeline."""

    def setUp(self):
        self.client = OrganizationAPIClient()
        self.organization = Organization.objects.create(
            company_name="Test Org for RateCon Integration",
            phone="5551234567",
            email="test-org@example.com",
        )
        self.user = OrganizationUser.objects.create_user(
            email="ratecon-test@example.com",
            password="testpass123",
        )
        self.user_profile = UserProfile.objects.create(
            user=self.user,
            organization=self.organization,
        )
        self.client.force_authenticate_with_org(self.user, self.organization)
        self._uploaded_s3_keys = []

    def tearDown(self):
        """Clean up uploaded S3 objects."""
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

    def _get_test_pdf(self):
        """Get the first PDF file from test_documents/."""
        for fname in os.listdir(TEST_DOCUMENTS_DIR):
            if fname.lower().endswith('.pdf'):
                path = os.path.join(TEST_DOCUMENTS_DIR, fname)
                with open(path, 'rb') as f:
                    return fname, f.read()
        self.fail("No PDF files found in test_documents/")

    def test_full_celery_pipeline(self):
        """Test the full RateCon parsing pipeline acting as frontend."""
        filename, pdf_bytes = self._get_test_pdf()

        # 1. Create session
        resp = self.client.post(
            reverse('ratecon-create-session'),
            data={},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        session_id = resp.data['session_id']
        self.assertIsNotNone(session_id)

        # 2. Register document (get presigned URL)
        resp = self.client.post(
            reverse('ratecon-document-upload'),
            data={
                'session_id': session_id,
                'filename': filename,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        document_id = resp.data['document_id']
        s3_key = resp.data['s3_key']
        presigned_url = resp.data['presigned_url']
        self._uploaded_s3_keys.append(s3_key)

        # 3. Upload to S3 via presigned URL
        upload_resp = requests.put(
            presigned_url,
            data=pdf_bytes,
            headers={'Content-Type': 'application/pdf'},
        )
        self.assertIn(
            upload_resp.status_code, [200, 204],
            f"S3 presigned PUT failed ({upload_resp.status_code}): {upload_resp.text}"
        )

        # 4. Mark upload complete
        resp = self.client.post(
            reverse('ratecon-upload-complete'),
            data={'document_id': document_id},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

        # 5. Trigger processing
        resp = self.client.post(
            reverse('ratecon-process-session', kwargs={'session_id': session_id}),
            data={'mode': 'sync'},
            format='json',
        )
        self.assertEqual(resp.status_code, 202)

        # 6. Poll for completion
        max_wait = 120  # seconds
        poll_interval = 2
        elapsed = 0
        terminal_statuses = {
            DocumentStatus.PARSED,
            DocumentStatus.MISCLASSIFIED,
            DocumentStatus.FAILED,
        }

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            doc = RateConDocument.objects.get(pk=document_id)
            if doc.status in terminal_statuses:
                break

        # 7. Assert
        doc = RateConDocument.objects.get(pk=document_id)
        self.assertEqual(
            doc.status,
            DocumentStatus.PARSED,
            f"Expected PARSED but got {doc.status}. Error: {doc.error_message}",
        )

        doc = RateConDocument.objects.select_related('load').get(pk=document_id)
        self.assertIsNotNone(
            doc.load,
            "RateConDocument.load should not be null after PARSED status",
        )

        # Print full load details
        load = doc.load
        print(f"\n{'='*60}")
        print(f"LOAD DETAILS (ID: {load.pk})")
        print(f"{'='*60}")
        print(f"  Reference #:    {load.reference_number}")
        print(f"  BOL #:          {load.bol_number}")
        print(f"  Customer:       {load.customer}")
        print(f"  Status:         {load.status}")
        print(f"  Billing Status: {load.billing_status}")
        print(f"  Trailer Type:   {load.trailer_type}")

        for leg in load.legs.prefetch_related('stops__address').all():
            print(f"\n  LEG {leg.pk}:")
            for stop in leg.stops.select_related('address').all():
                addr = stop.address
                print(f"    Stop #{stop.stop_number} [{stop.action} - {stop.get_action_display()}]")
                print(f"      Address:    {addr.street}, {addr.city}, {addr.state} {addr.zip_code}")
                if addr.place_name:
                    print(f"      Place:      {addr.place_name}")
                print(f"      Start:      {stop.start_range}")
                print(f"      End:        {stop.end_range}")
                if stop.po_numbers:
                    print(f"      PO #s:      {stop.po_numbers}")
                if stop.driver_notes:
                    print(f"      Notes:      {stop.driver_notes}")

        print(f"\n  Classification:")
        print(f"    Classification passed: {doc.classification_passed}")
        print(f"    Classification reason: {doc.classification_reason}")
        print(f"{'='*60}\n")

    def test_duplicate_filename_handling(self):
        """Test that uploading two documents with the same filename resolves duplicates."""
        filename = "duplicate_test.pdf"

        # Create session
        resp = self.client.post(
            reverse('ratecon-create-session'),
            data={},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        session_id = resp.data['session_id']

        # First upload
        resp1 = self.client.post(
            reverse('ratecon-document-upload'),
            data={'session_id': session_id, 'filename': filename},
            format='json',
        )
        self.assertEqual(resp1.status_code, 201)
        self.assertEqual(resp1.data['original_filename'], filename)

        # Second upload with same filename
        resp2 = self.client.post(
            reverse('ratecon-document-upload'),
            data={'session_id': session_id, 'filename': filename},
            format='json',
        )
        self.assertEqual(resp2.status_code, 201)
        self.assertEqual(resp2.data['original_filename'], 'duplicate_test-1.pdf')

        # Third upload
        resp3 = self.client.post(
            reverse('ratecon-document-upload'),
            data={'session_id': session_id, 'filename': filename},
            format='json',
        )
        self.assertEqual(resp3.status_code, 201)
        self.assertEqual(resp3.data['original_filename'], 'duplicate_test-2.pdf')

    def test_full_celery_pipeline_pdf_mode(self):
        """Test the full RateCon parsing pipeline using direct PDF mode (use_raw_text=False)."""
        filename, pdf_bytes = self._get_test_pdf()

        # 1. Create session
        resp = self.client.post(
            reverse('ratecon-create-session'),
            data={},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        session_id = resp.data['session_id']

        # 2. Register document (get presigned URL for upload)
        resp = self.client.post(
            reverse('ratecon-document-upload'),
            data={
                'session_id': session_id,
                'filename': filename,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        document_id = resp.data['document_id']
        s3_key = resp.data['s3_key']
        presigned_url = resp.data['presigned_url']
        self._uploaded_s3_keys.append(s3_key)

        # 3. Upload to S3 via presigned URL
        upload_resp = requests.put(
            presigned_url,
            data=pdf_bytes,
            headers={'Content-Type': 'application/pdf'},
        )
        self.assertIn(
            upload_resp.status_code, [200, 204],
            f"S3 presigned PUT failed ({upload_resp.status_code}): {upload_resp.text}"
        )

        # 4. Mark upload complete
        resp = self.client.post(
            reverse('ratecon-upload-complete'),
            data={'document_id': document_id},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

        # 5. Trigger processing via the PDF mode endpoint
        t_start = time.time()
        resp = self.client.post(
            reverse('ratecon-process-session-pdf', kwargs={'session_id': session_id}),
            data={'mode': 'sync'},
            format='json',
        )
        self.assertEqual(resp.status_code, 202)

        # 6. Poll for completion
        max_wait = 180
        poll_interval = 2
        elapsed = 0
        terminal_statuses = {
            DocumentStatus.PARSED,
            DocumentStatus.MISCLASSIFIED,
            DocumentStatus.FAILED,
        }

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            doc = RateConDocument.objects.get(pk=document_id)
            if doc.status in terminal_statuses:
                break

        t_end = time.time()
        processing_time = t_end - t_start

        # 7. Assert
        doc = RateConDocument.objects.get(pk=document_id)
        self.assertEqual(
            doc.status,
            DocumentStatus.PARSED,
            f"Expected PARSED but got {doc.status}. Error: {doc.error_message}",
        )

        doc = RateConDocument.objects.select_related('load').get(pk=document_id)
        self.assertIsNotNone(
            doc.load,
            "RateConDocument.load should not be null after PARSED status",
        )

        # Print results
        load = doc.load
        print(f"\n{'='*60}")
        print(f"PDF MODE LOAD DETAILS (ID: {load.pk})")
        print(f"{'='*60}")
        print(f"  Processing Time: {processing_time:.2f}s")
        print(f"  Reference #:    {load.reference_number}")
        print(f"  BOL #:          {load.bol_number}")
        print(f"  Customer:       {load.customer}")
        print(f"  Status:         {load.status}")
        print(f"  Billing Status: {load.billing_status}")
        print(f"  Trailer Type:   {load.trailer_type}")

        for leg in load.legs.prefetch_related('stops__address').all():
            print(f"\n  LEG {leg.pk}:")
            for stop in leg.stops.select_related('address').all():
                addr = stop.address
                print(f"    Stop #{stop.stop_number} [{stop.action} - {stop.get_action_display()}]")
                print(f"      Address:    {addr.street}, {addr.city}, {addr.state} {addr.zip_code}")
                if addr.place_name:
                    print(f"      Place:      {addr.place_name}")
                print(f"      Start:      {stop.start_range}")
                if stop.po_numbers:
                    print(f"      PO #s:      {stop.po_numbers}")
                if stop.driver_notes:
                    print(f"      Notes:      {stop.driver_notes}")

        print(f"\n  Classification:")
        print(f"    Classification passed: {doc.classification_passed}")
        print(f"    Classification reason: {doc.classification_reason}")
        print(f"\n  TOTAL TIME: {processing_time:.2f}s")
        print(f"{'='*60}\n")
