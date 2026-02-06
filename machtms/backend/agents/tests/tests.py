import os
from unittest import skipUnless
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from machtms.backend.agents.views import AgentChatView, AgentStreamView
from machtms.backend.auth.models import Organization


@override_settings(DEBUG=False)
class AgentChatViewTests(TestCase):
    """Tests for the non-streaming agent chat endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com",
        )

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AgentChatView.as_view()

    @patch('machtms.backend.agents.views.get_lead_agent')
    def test_chat_returns_200_with_valid_query(self, mock_get_agent):
        mock_result = MagicMock()
        mock_result.content = "Here is the information you requested."
        mock_agent = MagicMock()
        mock_agent.run.return_value = mock_result
        mock_get_agent.return_value = mock_agent

        request = self.factory.post(
            '/api/agents/chat/',
            {'query': 'What loads do we have?'},
            format='json',
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)

    def test_chat_returns_400_without_query(self):
        request = self.factory.post('/api/agents/chat/', {}, format='json')
        response = self.view(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)

    @patch('machtms.backend.agents.views.get_lead_agent')
    def test_chat_response_contains_content(self, mock_get_agent):
        mock_result = MagicMock()
        mock_result.content = "We have 5 active loads."
        mock_agent = MagicMock()
        mock_agent.run.return_value = mock_result
        mock_get_agent.return_value = mock_agent

        request = self.factory.post(
            '/api/agents/chat/',
            {'query': 'How many loads?'},
            format='json',
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn('response', response.data)
        self.assertEqual(response.data['response'], "We have 5 active loads.")


@override_settings(DEBUG=False)
class AgentStreamViewTests(TestCase):
    """Tests for the SSE streaming agent endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com",
        )

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AgentStreamView.as_view()

    @patch('machtms.backend.agents.views.get_lead_agent')
    def test_stream_returns_200_with_sse_content_type(self, mock_get_agent):
        mock_event = MagicMock()
        mock_event.content = "chunk"
        mock_agent = MagicMock()
        mock_agent.run.return_value = iter([mock_event])
        mock_get_agent.return_value = mock_agent

        request = self.factory.post(
            '/api/agents/stream/',
            {'query': 'Tell me about loads'},
            format='json',
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/event-stream')

    @patch('machtms.backend.agents.views.get_lead_agent')
    def test_stream_returns_data_events(self, mock_get_agent):
        mock_event1 = MagicMock()
        mock_event1.content = "Hello"
        mock_event2 = MagicMock()
        mock_event2.content = " world"
        mock_agent = MagicMock()
        mock_agent.run.return_value = iter([mock_event1, mock_event2])
        mock_get_agent.return_value = mock_agent

        request = self.factory.post(
            '/api/agents/stream/',
            {'query': 'Say hello'},
            format='json',
        )
        response = self.view(request)
        chunks = list(response.streaming_content)

        # Should have data events in SSE format
        self.assertTrue(any(b'data: ' in chunk for chunk in chunks))

    @patch('machtms.backend.agents.views.get_lead_agent')
    def test_stream_ends_with_done(self, mock_get_agent):
        mock_event = MagicMock()
        mock_event.content = "response"
        mock_agent = MagicMock()
        mock_agent.run.return_value = iter([mock_event])
        mock_get_agent.return_value = mock_agent

        request = self.factory.post(
            '/api/agents/stream/',
            {'query': 'Test query'},
            format='json',
        )
        response = self.view(request)
        chunks = list(response.streaming_content)

        last_chunk = chunks[-1]
        self.assertIn(b'[DONE]', last_chunk)

    def test_stream_returns_400_without_query(self):
        request = self.factory.post('/api/agents/stream/', {}, format='json')
        response = self.view(request)

        self.assertEqual(response.status_code, 400)


@skipUnless(os.environ.get('OPENAI_API_KEY'), "OPENAI_API_KEY not set")
@override_settings(DEBUG=False)
class AgentChatViewIntegrationTests(TestCase):
    """Integration tests that call the actual LLM through the views."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Test Trucking Co",
            phone="555-123-4567",
            email="dispatch@testtrucking.com",
        )

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_chat_view_with_real_agent(self):
        view = AgentChatView.as_view()
        request = self.factory.post(
            '/api/agents/chat/',
            {'query': 'Hello, what can you help me with?'},
            format='json',
        )
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn('response', response.data)
        self.assertTrue(len(response.data['response']) > 0)

    def test_stream_view_with_real_agent(self):
        view = AgentStreamView.as_view()
        request = self.factory.post(
            '/api/agents/stream/',
            {'query': 'Hello, what can you help me with?'},
            format='json',
        )
        response = view(request)

        self.assertEqual(response.status_code, 200)
        chunks = list(response.streaming_content)
        self.assertTrue(len(chunks) > 0)
        self.assertIn(b'[DONE]', chunks[-1])
