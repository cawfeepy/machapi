from knox.auth import TokenAuthentication
from machtms.core.auth.permissions import check_is_localhost


class TMSAuthentication(TokenAuthentication):
    def authenticate(self, request):
        # if check_is_localhost(request):
        #     return None

        if 'auth_token' in request.COOKIES and \
                'HTTP_AUTHORIZATION' not in request.META:
            return self.authenticate_credentials(
                request.COOKIES.get('auth_token').encode('utf-8')
            )
        return super().authenticate(request)
