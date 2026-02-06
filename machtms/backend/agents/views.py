import logging

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from machtms.agents.members import lead_team
from machtms.backend.auth.models import Organization
from machtms.core.envctrl import env

logger = logging.getLogger(__name__)


def _get_organization(request: Request) -> Organization | None:
    """Resolve organization from request context.

    For authenticated users with a profile, use their organization.
    For test/management-command usage (AllowAny), fall back to the
    first available organization.
    """
    if hasattr(request, 'user') and request.user.is_authenticated:
        profile = getattr(request.user, 'userprofile', None)
        if profile and profile.organization:
            return profile.organization
    if env.django.DEBUG:
        return Organization.objects.first()
    raise Exception('Something went wrong retrieving an organization.')


class AgentChatView(APIView):
    """Non-streaming POST endpoint for agent chat."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        query = request.data.get('query')
        if not query:
            return Response(
                {'error': 'query field is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = _get_organization(request)
        if not organization:
            return Response(
                {'error': 'No organization available'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = lead_team.run(query, dependencies={"organization": organization})
            return Response({'response': result.content})
        except Exception:
            logger.exception('Agent chat error')
            return Response(
                {'error': 'Agent processing failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AgentStreamView(APIView):
    """SSE streaming POST endpoint for agent chat."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> StreamingHttpResponse | Response:
        query = request.data.get('query')
        if not query:
            return Response(
                {'error': 'query field is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = _get_organization(request)
        if not organization:
            return Response(
                {'error': 'No organization available'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        def event_stream():
            try:
                result = lead_team.run(query, stream=True, dependencies={"organization": organization})
                for event in result:
                    event_type = getattr(event, 'event', None)
                    # Only yield team-level content to avoid duplicating
                    # member agent responses alongside the lead's summary.
                    if event_type == 'TeamRunContent' and event.content:
                        yield f"data: {event.content}\n\n"
                yield "data: [DONE]\n\n"
            except Exception:
                logger.exception('Agent stream error')
                yield "data: [ERROR] Agent processing failed\n\n"
                yield "data: [DONE]\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
