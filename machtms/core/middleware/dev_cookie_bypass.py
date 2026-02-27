import logging
import sys

from django.conf import settings
from knox.auth import TokenAuthentication as KnoxTokenAuthentication
from knox.models import AuthToken
from rest_framework.exceptions import AuthenticationFailed

from machtms.backend.auth.models import OrganizationUser
from machtms.core.envctrl import env

logger = logging.getLogger(__name__)


class CookieAutomaticBypassMiddleware:
    """
    DEV ONLY: Auto-authenticates requests when no valid auth_token cookie exists.

    On each request:
    - If no cookie or the cookie's token is expired/invalid, creates a fresh
      Knox AuthToken for the first OrganizationUser, injects the Authorization
      header into the request, and sets the cookie on the response.
    - If a valid cookie exists, does nothing.

    Disabled during test runs so tests can verify unauthenticated behavior.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.DEBUG or 'test' in sys.argv:
            return self.get_response(request)

        token_value = None
        existing_cookie = request.COOKIES.get('auth_token')

        needs_new_token = (
            existing_cookie is None
            or not self._is_valid_token(existing_cookie)
        )

        if needs_new_token:
            token_value = self._create_dev_token(request)
            if token_value:
                request.META['HTTP_AUTHORIZATION'] = f'Token {token_value}'

        response = self.get_response(request)

        if token_value is not None:
            domain = None if settings.DEBUG else f'.{env.django.HOST}'
            response.set_cookie(
                'auth_token',
                token_value,
                samesite='Lax',
                httponly=False,
                secure=False,
                domain=domain,
            )

        return response

    def _is_valid_token(self, token_str):
        try:
            KnoxTokenAuthentication().authenticate_credentials(
                token_str.encode('utf-8')
            )
            return True
        except AuthenticationFailed:
            return False

    def _create_dev_token(self, request):
        user = OrganizationUser.objects.first()
        if user is None:
            logger.warning(
                "CookieAutomaticBypassMiddleware: No OrganizationUser found"
            )
            return None
        try:
            request.organization = user.userprofile.organization.id
        except Exception:
            request.organization = None
        _, token_value = AuthToken.objects.create(user)
        logger.info(
            "CookieAutomaticBypassMiddleware: Created dev token for %s",
            user.email,
        )
        return token_value
