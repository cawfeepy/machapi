"""
Test utilities for machTMS.

This module provides base test classes and utilities that handle
organization-aware authentication properly in tests.
"""
from rest_framework.test import APITestCase, APIClient


class OrganizationAPIClient(APIClient):
    """
    Custom API client that properly sets request.organization after authentication.

    The standard force_authenticate() sets the user during DRF's view dispatch,
    but OrganizationMiddleware runs before that and sees AnonymousUser.
    This client injects organization into the request via a custom handler.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization_id = None

    def force_authenticate_with_org(self, user, organization):
        """
        Authenticate the client with both user and organization.

        Args:
            user: The user to authenticate as
            organization: The organization instance (will use its id)
        """
        self.force_authenticate(user=user)
        self._organization_id = organization.id if hasattr(organization, 'id') else organization

    def generic(self, method, path, data='', content_type='application/octet-stream',
                secure=False, **extra):
        """
        Override generic to inject organization into WSGI environ.

        The organization ID is passed via a custom header that our
        test middleware can read.
        """
        if self._organization_id is not None:
            extra['HTTP_X_TEST_ORGANIZATION_ID'] = str(self._organization_id)
        return super().generic(method, path, data, content_type, secure, **extra)


class OrganizationTestMiddleware:
    """
    Test middleware that sets request.organization from a custom header.

    This middleware should be added to MIDDLEWARE in test settings and
    should run AFTER OrganizationMiddleware to override the organization
    when the test header is present.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check for test organization header
        test_org_id = request.META.get('HTTP_X_TEST_ORGANIZATION_ID')
        if test_org_id is not None:
            try:
                request.organization = int(test_org_id)
            except (ValueError, TypeError):
                pass

        return self.get_response(request)


class OrganizationAPITestCase(APITestCase):
    """
    Base test case for API tests that require organization context.

    This test case provides helper methods to properly authenticate
    users with their organization context, working around the timing
    issue between Django middleware and DRF authentication.

    IMPORTANT: Add 'machtms.core.testing.OrganizationTestMiddleware' to
    your MIDDLEWARE setting (after OrganizationMiddleware) for this to work.

    Usage:
        class MyTests(OrganizationAPITestCase):
            @classmethod
            def setUpTestData(cls):
                cls.organization = Organization.objects.create(...)
                cls.user = OrganizationUser.objects.create_user(...)
                cls.user_profile = UserProfile.objects.create(
                    user=cls.user,
                    organization=cls.organization
                )

            def setUp(self):
                self.authenticate(self.user, self.organization)
    """

    client_class = OrganizationAPIClient

    def authenticate(self, user, organization):
        """
        Authenticate the test client with user and organization.

        This method should be called in setUp() after setting up
        the user and organization in setUpTestData().

        Args:
            user: The OrganizationUser to authenticate as
            organization: The Organization instance
        """
        self.client.force_authenticate_with_org(user, organization)

    def unauthenticate(self):
        """Remove authentication from the test client."""
        self.client.force_authenticate(user=None)
        self.client._organization_id = None
