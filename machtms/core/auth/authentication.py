import logging

from django.conf import settings
from knox.auth import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)


class TMSAuthentication(TokenAuthentication):
    def authenticate(self, request):
        if 'auth_token' in request.COOKIES and \
                'HTTP_AUTHORIZATION' not in request.META:
            result = self.authenticate_credentials(
                request.COOKIES.get('auth_token').encode('utf-8')
            )
        else:
            result = super().authenticate(request)

        if result is not None:
            user, token = result
            try:
                request.organization = user.userprofile.organization.id
            except Exception:
                if not settings.DEBUG and not user.is_superuser:
                    raise AuthenticationFailed(
                        "User is not associated with an organization."
                    )
                request.organization = None

        return result
