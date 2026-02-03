class OrganizationMiddleware(object):
    """
    Middleware to attach the organization of an authenticated user's userprofile
    to the request as `request.organization`.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if the user is authenticated and has a userprofile with an organization.
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                request.organization = request.user.userprofile.organization.id
            except Exception:
                # If any issue arises (e.g., no userprofile exists), set organization to None.
                request.organization = None
        else:
            request.organization = None

        # Continue processing the request.
        response = self.get_response(request)
        return response
