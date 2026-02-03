from django.conf import settings
from rest_framework import serializers


class CurrentOrganizationDefault:
    requires_context = True

    def __call__(self, serializer_field):
        from machtms.backend.auth.models import Organization

        request = serializer_field.context['request']
        user = request.user

        # 1. Try to get the organization from the user (via userprofile)
        org = None
        if hasattr(user, 'userprofile') and hasattr(user.userprofile, 'organization'):
            org = user.userprofile.organization

        # 2. Fall back to request.organization (set by middleware or tests)
        if org is None:
            org_id = getattr(request, 'organization', None)
            if org_id is not None:
                try:
                    org = Organization.objects.get(pk=org_id)
                except Organization.DoesNotExist:
                    org = None

        # 3. If the user has an org, always return it (Prod & Dev)
        if org:
            return org

        # 4. If no org is found, check if we are in DEBUG/Dev mode
        # If True, return None. This effectively makes the field "optional"
        if settings.DEBUG:
            return None

        # 5. If in Prod and no org, raise a validation error
        raise serializers.ValidationError(
            "Action not allowed: User is not associated with an organization."
        )

    def __repr__(self):
        return '%s()' % self.__class__.__name__
