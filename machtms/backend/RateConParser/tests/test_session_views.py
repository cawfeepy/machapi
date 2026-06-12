"""
Tests for SessionListView and HideSessionView.

Covers:
- GET /ratecon/sessions/list/   — SessionListView
- POST /ratecon/sessions/<id>/hide/  — HideSessionView
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from machtms.core.testing import OrganizationAPITestCase
from machtms.backend.auth.models import Organization, OrganizationUser, UserProfile
from machtms.backend.RateConParser.models import ParsingSession, RateConDocument, SessionStatus, DocumentStatus


LIST_URL = reverse('ratecon-session-list')


def _hide_url(session_id):
    return reverse('ratecon-hide-session', kwargs={'session_id': session_id})


def _make_org(company_name, email):
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
    return org, user


# ---------------------------------------------------------------------------
# SessionListView
# ---------------------------------------------------------------------------

class SessionListViewTests(OrganizationAPITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.organization, cls.user = _make_org("List Org", "list@example.com")

    def setUp(self):
        self.authenticate(self.user, self.organization)

    # --- helpers ---

    def _make_session(self, **kwargs):
        kwargs.setdefault('organization', self.organization)
        kwargs.setdefault('status', SessionStatus.UPLOADING)
        return ParsingSession.objects.create(**kwargs)

    # --- tests ---

    def test_returns_200(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)

    def test_returns_empty_list_when_no_sessions(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_excludes_hidden_sessions(self):
        self._make_session(is_hidden=True)
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_max_8_sessions_returned(self):
        for _ in range(10):
            self._make_session()
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 8)

    def test_ordered_newest_first(self):
        now = timezone.now()
        sessions = []
        for i in range(3):
            s = self._make_session()
            # stagger created_at so ordering is deterministic
            ParsingSession.objects.filter(pk=s.pk).update(
                created_at=now - timedelta(seconds=10 - i)
            )
            sessions.append(s.pk)

        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        returned_ids = [item['id'] for item in response.data]
        # newest first → sessions[-1] (i=2, least offset) should be first
        self.assertEqual(returned_ids, list(reversed(sessions)))

    def test_org_isolation(self):
        other_org, other_user = _make_org("Other Org", "other@example.com")
        ParsingSession.objects.create(
            organization=other_org,
            status=SessionStatus.UPLOADING,
        )
        # our org has no sessions
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_is_hidden_field_present_in_response(self):
        self._make_session()
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)
        for item in response.data:
            self.assertIn('is_hidden', item)

    def test_documents_field_present_in_response(self):
        session = self._make_session()
        RateConDocument.objects.create(
            organization=self.organization,
            session=session,
            status=DocumentStatus.PENDING,
            original_filename='test_rc.pdf',
            s3_key='some/key.pdf',
        )
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)
        first = response.data[0]
        self.assertIn('documents', first)
        filenames = [doc['original_filename'] for doc in first['documents']]
        self.assertIn('test_rc.pdf', filenames)

    def test_unauthenticated_returns_401(self):
        self.unauthenticate()
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 401)


# ---------------------------------------------------------------------------
# HideSessionView
# ---------------------------------------------------------------------------

class HideSessionViewTests(OrganizationAPITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.organization, cls.user = _make_org("Hide Org", "hide@example.com")

    def setUp(self):
        self.authenticate(self.user, self.organization)

    def _make_session(self, **kwargs):
        kwargs.setdefault('organization', self.organization)
        kwargs.setdefault('status', SessionStatus.UPLOADING)
        return ParsingSession.objects.create(**kwargs)

    def test_returns_200_with_correct_shape(self):
        session = self._make_session()
        response = self.client.post(_hide_url(session.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['session_id'], session.pk)
        self.assertTrue(response.data['is_hidden'])

    def test_sets_is_hidden_true_in_db(self):
        session = self._make_session()
        self.client.post(_hide_url(session.pk))
        session.refresh_from_db()
        self.assertTrue(session.is_hidden)

    def test_hidden_session_excluded_from_list(self):
        session = self._make_session()
        self.client.post(_hide_url(session.pk))
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        returned_ids = [item['id'] for item in response.data]
        self.assertNotIn(session.pk, returned_ids)

    def test_cannot_hide_other_orgs_session(self):
        other_org, _ = _make_org("Other Org 2", "other2@example.com")
        other_session = ParsingSession.objects.create(
            organization=other_org,
            status=SessionStatus.UPLOADING,
        )
        response = self.client.post(_hide_url(other_session.pk))
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_returns_401(self):
        session = self._make_session()
        self.unauthenticate()
        response = self.client.post(_hide_url(session.pk))
        self.assertEqual(response.status_code, 401)
