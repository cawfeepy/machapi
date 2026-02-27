class OrganizationMiddleware(object):
    """
    Initializes request.organization to None on every request.

    The actual org resolution happens later in TMSAuthentication (DRF view level)
    or CookieAutomaticBypassMiddleware (dev mode). This middleware ensures the
    attribute always exists so downstream code never hits AttributeError.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None
        response = self.get_response(request)
        return response
