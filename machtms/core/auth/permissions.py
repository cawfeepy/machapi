from rest_framework.permissions import BasePermission
from rest_framework.request import HttpRequest
from rest_framework import permissions
from rest_framework_api_key.permissions import BaseHasAPIKey
from machtms.backend.auth.models import OrganizationAPIKey


def check_is_localhost(request):
        allowed_hosts = ['127.0.0.1']

        remote_addr = request.META.get('REMOTE_ADDR', '')
        host = request.get_host().split(':')[0]  # Extract host without port
        if remote_addr in allowed_hosts or host in allowed_hosts:
            return True


class LocalhostPermission(BasePermission):
    """
    Custom permission to only allow access from 127.0.0.1.
    """
    def has_permission(self, request: HttpRequest, view):
        return request.META.get('REMOTE_ADDR') == '127.0.0.1'


class TMSCustomPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        # if check_is_localhost(request):
        #     return True
        #
        # if request.user \
        #         and request.method == 'GET' \
        #         and view.action == 'list':
        #     return True

        # Otherwise, only allow authenticated requests
        # Post Django 1.10, 'is_authenticated' is a read-only attribute
        return request.user and request.user.is_authenticated


class OrgAPIPermission(BaseHasAPIKey):
    model = OrganizationAPIKey
