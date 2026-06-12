"""
Tests for the PresignedURLEntryPoint workflow.

Covers:
- PresignedURLEntryPoint model: field defaults, status choices
- _deduplicate_filename helper
- POST /ratecon/presigned-urls/           — PresignedURLEntryPointView
- POST /ratecon/sessions/from-presigned/  — CreateSessionFromPresignedView
- POST /ratecon/orphaned/pre-check/       — OrphanedDocumentCheckView (dispatches task, returns 202)
- _process_orphaned_entrypoints helper: all 4 orphan cases
- Celery task: run_orphan_check_for_org
"""

import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from machtms.core.testing import OrganizationAPIClient
from machtms.backend.auth.models import Organization, OrganizationUser, UserProfile
from machtms.backend.RateConParser.models import (
    ParsingSession,
    DocumentStatus,
    PresignedURLEntryPoint,
    PresignedURLEntryPointStatus,
)
from machtms.backend.RateConParser.views import _deduplicate_filename, _process_orphaned_entrypoints


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_org_and_client(company_name="Test Org", email="test@example.com"):
    org = Organization.objects.create(
        company_name=company_name,
        phone="5550001111",
        email=email,
    )
    user = OrganizationUser.objects.create_user(
        email=f"user-{email}",
        password="testpass123",
    )
    UserProfile.objects.create(user=user, organization=org)
    client = OrganizationAPIClient()
    client.force_authenticate_with_org(user, org)
    return org, client


def make_entry(org, *, filename="doc.pdf", status=PresignedURLEntryPointStatus.ORPHANED,
               expired=False):
    expiration = timezone.now() + (timedelta(seconds=-1) if expired else timedelta(seconds=900))
    return PresignedURLEntryPoint.objects.create(
        organization=org,
        presigned_url="https://s3.example.com/fake-presigned",
        s3_key=f"fake-key-{filename}",
        filename=filename,
        expiration=expiration,
        status=status,
    )


# ---------------------------------------------------------------------------
# Model unit tests
# ---------------------------------------------------------------------------

class PresignedURLEntryPointModelTest(TestCase):

    def setUp(self):
        self.org = Organization.objects.create(
            company_name="Model Test Org",
            phone="5550000000",
            email="model@test.com",
        )

    def test_default_status_is_orphaned(self):
        entry = PresignedURLEntryPoint.objects.create(
            organization=self.org,
            presigned_url="https://example.com/url",
            s3_key="some-key.pdf",
            filename="file.pdf",
            expiration=timezone.now() + timedelta(seconds=900),
        )
        self.assertEqual(entry.status, PresignedURLEntryPointStatus.ORPHANED)

    def test_status_choices_exist(self):
        choices = {c[0] for c in PresignedURLEntryPointStatus.choices}
        self.assertIn('orphaned', choices)
        self.assertIn('processed', choices)

    def test_str_representation(self):
        entry = make_entry(self.org, filename="invoice.pdf")
        self.assertIn("invoice.pdf", str(entry))
        self.assertIn("orphaned", str(entry))

    def test_expiration_stored_correctly(self):
        future = timezone.now() + timedelta(seconds=900)
        entry = PresignedURLEntryPoint.objects.create(
            organization=self.org,
            presigned_url="https://example.com/url",
            s3_key="key.pdf",
            filename="file.pdf",
            expiration=future,
        )
        self.assertAlmostEqual(
            entry.expiration.timestamp(),
            future.timestamp(),
            delta=2,
        )


# ---------------------------------------------------------------------------
# _deduplicate_filename helper
# ---------------------------------------------------------------------------

class DeduplicateFilenameTest(TestCase):

    def test_first_occurrence_unchanged(self):
        seen = set()
        result = _deduplicate_filename("report.pdf", seen)
        self.assertEqual(result, "report.pdf")
        self.assertIn("report.pdf", seen)

    def test_second_occurrence_gets_suffix(self):
        seen = {"report.pdf"}
        result = _deduplicate_filename("report.pdf", seen)
        self.assertEqual(result, "report-2.pdf")

    def test_third_occurrence(self):
        seen = {"report.pdf", "report-2.pdf"}
        result = _deduplicate_filename("report.pdf", seen)
        self.assertEqual(result, "report-3.pdf")

    def test_different_extensions(self):
        seen = set()
        _deduplicate_filename("a.pdf", seen)
        _deduplicate_filename("a.pdf", seen)
        result = _deduplicate_filename("a.pdf", seen)
        self.assertEqual(result, "a-3.pdf")


# ---------------------------------------------------------------------------
# PresignedURLEntryPointView  POST /ratecon/presigned-urls/
# ---------------------------------------------------------------------------

@patch('machtms.backend.RateConParser.views.s3.generate_presigned_url')
class PresignedURLEntryPointViewTest(TestCase):

    def setUp(self):
        self.org, self.client = make_org_and_client("PresignedView Org", "pv@test.com")
        self.url = reverse('ratecon-presigned-urls')

    def test_creates_entrypoints_and_returns_201(self, mock_presigned):
        mock_presigned.return_value = "https://fake-presigned-url.example.com"

        response = self.client.post(
            self.url,
            data=json.dumps({'files': [
                {'filename': 'doc1.pdf', 'mime_type': 'application/pdf'},
                {'filename': 'doc2.pdf', 'mime_type': 'application/pdf'},
            ]}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(PresignedURLEntryPoint.objects.filter(organization=self.org).count(), 2)

    def test_entrypoints_have_orphaned_status(self, mock_presigned):
        mock_presigned.return_value = "https://fake.url"

        self.client.post(
            self.url,
            data=json.dumps({'files': [{'filename': 'a.pdf'}]}),
            content_type='application/json',
        )

        entry = PresignedURLEntryPoint.objects.get(organization=self.org)
        self.assertEqual(entry.status, PresignedURLEntryPointStatus.ORPHANED)

    def test_filenames_deduplicated_within_batch(self, mock_presigned):
        mock_presigned.return_value = "https://fake.url"

        self.client.post(
            self.url,
            data=json.dumps({'files': [
                {'filename': 'invoice.pdf'},
                {'filename': 'invoice.pdf'},
                {'filename': 'invoice.pdf'},
            ]}),
            content_type='application/json',
        )

        filenames = list(
            PresignedURLEntryPoint.objects.filter(organization=self.org)
            .values_list('filename', flat=True)
            .order_by('id')
        )
        self.assertIn('invoice.pdf', filenames)
        self.assertIn('invoice-2.pdf', filenames)
        self.assertIn('invoice-3.pdf', filenames)

    def test_presigned_url_in_response(self, mock_presigned):
        mock_presigned.return_value = "https://special-url.example.com/key"

        response = self.client.post(
            self.url,
            data=json.dumps({'files': [{'filename': 'test.pdf'}]}),
            content_type='application/json',
        )

        self.assertEqual(response.json()[0]['presigned_url'], "https://special-url.example.com/key")

    def test_expiration_within_15_minutes(self, mock_presigned):
        mock_presigned.return_value = "https://fake.url"

        before = timezone.now()
        self.client.post(
            self.url,
            data=json.dumps({'files': [{'filename': 'exp.pdf'}]}),
            content_type='application/json',
        )
        after = timezone.now()

        entry = PresignedURLEntryPoint.objects.get(organization=self.org)
        self.assertGreaterEqual(entry.expiration, before + timedelta(seconds=900))
        self.assertLessEqual(entry.expiration, after  + timedelta(seconds=900))

    def test_empty_files_list_returns_201_with_empty_list(self, mock_presigned):
        response = self.client.post(
            self.url,
            data=json.dumps({'files': []}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), [])


# ---------------------------------------------------------------------------
# CreateSessionFromPresignedView  POST /ratecon/sessions/from-presigned/
# ---------------------------------------------------------------------------

class CreateSessionFromPresignedViewTest(TestCase):

    def setUp(self):
        self.org, self.client = make_org_and_client("FromPresigned Org", "fp@test.com")
        self.url = reverse('ratecon-session-from-presigned')

    def test_creates_session_and_documents(self):
        e1 = make_entry(self.org, filename="a.pdf")
        e2 = make_entry(self.org, filename="b.pdf")

        response = self.client.post(
            self.url,
            data=json.dumps({'entrypoint_ids': [e1.pk, e2.pk]}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn('session_id', data)
        self.assertEqual(len(data['documents']), 2)

        session = ParsingSession.objects.get(pk=data['session_id'])
        self.assertEqual(session.organization, self.org)
        self.assertEqual(session.documents.count(), 2)

    def test_entrypoints_marked_processed(self):
        e1 = make_entry(self.org, filename="x.pdf")

        self.client.post(
            self.url,
            data=json.dumps({'entrypoint_ids': [e1.pk]}),
            content_type='application/json',
        )

        e1.refresh_from_db()
        self.assertEqual(e1.status, PresignedURLEntryPointStatus.PROCESSED)

    def test_documents_have_pending_status(self):
        e1 = make_entry(self.org, filename="pending.pdf")

        response = self.client.post(
            self.url,
            data=json.dumps({'entrypoint_ids': [e1.pk]}),
            content_type='application/json',
        )

        session = ParsingSession.objects.get(pk=response.json()['session_id'])
        doc = session.documents.get()
        self.assertEqual(doc.status, DocumentStatus.PENDING)

    def test_filenames_deduplicated_across_session(self):
        e1 = make_entry(self.org, filename="report.pdf")
        e2 = make_entry(self.org, filename="report.pdf")

        response = self.client.post(
            self.url,
            data=json.dumps({'entrypoint_ids': [e1.pk, e2.pk]}),
            content_type='application/json',
        )

        session = ParsingSession.objects.get(pk=response.json()['session_id'])
        filenames = set(session.documents.values_list('original_filename', flat=True))
        self.assertIn('report.pdf', filenames)
        self.assertIn('report-2.pdf', filenames)

    def test_returns_400_when_no_valid_entrypoints(self):
        response = self.client.post(
            self.url,
            data=json.dumps({'entrypoint_ids': [99999]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_ignores_already_processed_entrypoints(self):
        processed = make_entry(self.org, filename="done.pdf", status=PresignedURLEntryPointStatus.PROCESSED)
        orphaned  = make_entry(self.org, filename="todo.pdf")

        response = self.client.post(
            self.url,
            data=json.dumps({'entrypoint_ids': [processed.pk, orphaned.pk]}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()['documents']), 1)

    def test_ignores_entrypoints_from_other_org(self):
        other_org, _ = make_org_and_client("Other Org", "other@test.com")
        foreign = make_entry(other_org, filename="foreign.pdf")
        own     = make_entry(self.org,  filename="own.pdf")

        response = self.client.post(
            self.url,
            data=json.dumps({'entrypoint_ids': [foreign.pk, own.pk]}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()['documents']), 1)


# ---------------------------------------------------------------------------
# OrphanedDocumentCheckView  POST /ratecon/orphaned/pre-check/
# Dispatches a task and returns 202 — no synchronous DB changes.
# ---------------------------------------------------------------------------

@patch('machtms.core.celerycontroller.controller.CeleryController')
class OrphanedDocumentCheckViewTest(TestCase):

    def setUp(self):
        self.org, self.client = make_org_and_client("Orphan Check Org", "oc@test.com")
        self.url = reverse('ratecon-orphaned-precheck')

    def test_returns_202(self, MockController):
        response = self.client.post(self.url, content_type='application/json')
        self.assertEqual(response.status_code, 202)

    def test_response_body_contains_detail(self, MockController):
        response = self.client.post(self.url, content_type='application/json')
        self.assertIn('detail', response.json())

    def test_dispatches_celery_task(self, MockController):
        self.client.post(self.url, content_type='application/json')
        MockController.return_value.delay.assert_called_once()

    def test_task_called_with_org_id(self, MockController):
        from machtms.backend.RateConParser.tasks import run_orphan_check_for_org

        self.client.post(self.url, content_type='application/json')

        args = MockController.return_value.delay.call_args[0]
        # First arg is the task, second is org_id
        self.assertEqual(args[0], run_orphan_check_for_org)
        self.assertEqual(args[1], self.org.pk)

    def test_does_not_create_sessions_synchronously(self, MockController):
        """View must not touch the DB for session creation — that's the task's job."""
        make_entry(self.org, filename="orphan.pdf")

        self.client.post(self.url, content_type='application/json')

        self.assertEqual(ParsingSession.objects.count(), 0)


# ---------------------------------------------------------------------------
# _process_orphaned_entrypoints helper — all 4 cases
# ---------------------------------------------------------------------------

@patch('machtms.core.utils.s3_utils.s3_client')
@patch('machtms.core.celerycontroller.controller.CeleryController')
class ProcessOrphanedEntrypointsHelperTest(TestCase):

    def setUp(self):
        self.org = Organization.objects.create(
            company_name="Helper Test Org", phone="5550003", email="helper@test.com"
        )

    # --- Case A: expired + orphaned ---

    def test_expired_orphaned_deleted_from_db(self, MockController, mock_s3):
        entry = make_entry(self.org, filename="expired.pdf", expired=True)

        _process_orphaned_entrypoints(organization=self.org)

        self.assertFalse(PresignedURLEntryPoint.objects.filter(pk=entry.pk).exists())

    def test_expired_orphaned_triggers_s3_delete(self, MockController, mock_s3):
        entry = make_entry(self.org, filename="expired2.pdf", expired=True)

        _process_orphaned_entrypoints(organization=self.org)

        mock_s3.delete_object.assert_called_once()
        self.assertEqual(mock_s3.delete_object.call_args[1]['Key'], entry.s3_key)

    def test_expired_deleted_count(self, MockController, mock_s3):
        make_entry(self.org, filename="e1.pdf", expired=True)
        make_entry(self.org, filename="e2.pdf", expired=True)

        result = _process_orphaned_entrypoints(organization=self.org)

        self.assertEqual(result['expired_deleted'], 2)

    def test_s3_delete_exception_does_not_abort_recovery(self, MockController, mock_s3):
        """S3 failure must be swallowed so other entries are still processed."""
        mock_s3.delete_object.side_effect = Exception("S3 unavailable")
        make_entry(self.org, filename="broken.pdf", expired=True)
        make_entry(self.org, filename="valid.pdf")   # unexpired orphan

        result = _process_orphaned_entrypoints(organization=self.org)

        # Expired entry removed from DB despite S3 error
        self.assertEqual(PresignedURLEntryPoint.objects.filter(
            filename="broken.pdf", organization=self.org
        ).count(), 0)
        # Unexpired entry recovered
        self.assertEqual(result['recovered_count'], 1)

    # --- Case B: unexpired + orphaned ---

    def test_unexpired_orphaned_creates_session(self, MockController, mock_s3):
        make_entry(self.org, filename="fresh.pdf")

        result = _process_orphaned_entrypoints(organization=self.org)

        self.assertEqual(result['recovered_count'], 1)
        self.assertEqual(len(result['sessions_created']), 1)
        self.assertEqual(ParsingSession.objects.filter(organization=self.org).count(), 1)

    def test_unexpired_orphaned_entry_marked_processed(self, MockController, mock_s3):
        entry = make_entry(self.org, filename="will-be-processed.pdf")

        _process_orphaned_entrypoints(organization=self.org)

        entry.refresh_from_db()
        self.assertEqual(entry.status, PresignedURLEntryPointStatus.PROCESSED)

    def test_unexpired_orphaned_session_has_pending_doc(self, MockController, mock_s3):
        make_entry(self.org, filename="pending.pdf")

        result = _process_orphaned_entrypoints(organization=self.org)

        session = result['sessions_created'][0]
        doc = session.documents.get()
        self.assertEqual(doc.status, DocumentStatus.PENDING)

    def test_celery_task_dispatched_for_recovered_session(self, MockController, mock_s3):
        make_entry(self.org, filename="auto.pdf")

        _process_orphaned_entrypoints(organization=self.org)

        MockController.return_value.delay.assert_called_once()

    # --- Case C/D: processed entries cleaned up ---

    def test_processed_entry_deleted(self, MockController, mock_s3):
        entry = make_entry(self.org, filename="done.pdf", status=PresignedURLEntryPointStatus.PROCESSED)

        _process_orphaned_entrypoints(organization=self.org)

        self.assertFalse(PresignedURLEntryPoint.objects.filter(pk=entry.pk).exists())

    def test_expired_processed_entry_deleted(self, MockController, mock_s3):
        entry = make_entry(
            self.org, filename="expired-done.pdf",
            status=PresignedURLEntryPointStatus.PROCESSED,
            expired=True,
        )

        _process_orphaned_entrypoints(organization=self.org)

        self.assertFalse(PresignedURLEntryPoint.objects.filter(pk=entry.pk).exists())

    # --- Org scoping ---

    def test_does_not_touch_other_org_entries(self, MockController, mock_s3):
        other_org = Organization.objects.create(
            company_name="Other Org", phone="5550004", email="other@test.com"
        )
        other_entry = make_entry(other_org, filename="other.pdf", expired=True)

        _process_orphaned_entrypoints(organization=self.org)

        self.assertTrue(PresignedURLEntryPoint.objects.filter(pk=other_entry.pk).exists())


# ---------------------------------------------------------------------------
# run_orphan_check_for_org Celery task
# ---------------------------------------------------------------------------

@patch('machtms.core.utils.s3_utils.s3_client')
@patch('machtms.core.celerycontroller.controller.CeleryController')
class RunOrphanCheckForOrgTaskTest(TestCase):

    def setUp(self):
        self.org = Organization.objects.create(
            company_name="Task Org", phone="5550005", email="task@test.com"
        )

    def _run_task(self, org_id):
        from machtms.backend.RateConParser.tasks import run_orphan_check_for_org
        run_orphan_check_for_org.apply(args=[org_id])

    def test_processes_orphaned_entries_for_org(self, MockController, mock_s3):
        make_entry(self.org, filename="task-doc.pdf")

        self._run_task(self.org.pk)

        self.assertEqual(ParsingSession.objects.filter(organization=self.org).count(), 1)

    def test_deletes_expired_orphans(self, MockController, mock_s3):
        make_entry(self.org, filename="exp.pdf", expired=True)

        self._run_task(self.org.pk)

        self.assertEqual(PresignedURLEntryPoint.objects.filter(organization=self.org).count(), 0)

    def test_unknown_org_id_logs_warning_and_does_not_raise(self, MockController, mock_s3):
        # Should complete without error even if org doesn't exist
        self._run_task(org_id=999999)
        self.assertEqual(ParsingSession.objects.count(), 0)

    def test_does_not_process_other_orgs(self, MockController, mock_s3):
        other_org = Organization.objects.create(
            company_name="Other Task Org", phone="5550006", email="other-task@test.com"
        )
        make_entry(other_org, filename="other.pdf")

        self._run_task(self.org.pk)

        # Other org's entry untouched
        self.assertEqual(ParsingSession.objects.filter(organization=other_org).count(), 0)
