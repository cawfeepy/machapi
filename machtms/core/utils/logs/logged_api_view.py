import logging
from functools import wraps
from rest_framework.decorators import api_view
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def logged_api_view(http_method_names):
    """
    A decorator that wraps DRF's @api_view with logging functionality.

    Logs:
    - Successful responses (status < 400) as INFO
    - Client errors (400-499) as WARNING
    - Server errors (500+) as ERROR
    - Exceptions with full traceback as ERROR

    Usage:
        @logged_api_view(['GET'])
        def my_view(request):
            return Response({'message': 'Hello'})

        @logged_api_view(['POST', 'PUT'])
        def my_other_view(request):
            return Response({'created': True}, status=201)

    Args:
        http_method_names: List of allowed HTTP methods (e.g., ['GET', 'POST'])

    Returns:
        Decorated view function with logging enabled
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            view_name = view_func.__name__
            method = request.method

            try:
                response = view_func(request, *args, **kwargs)

                if response.status_code < 400:
                    logger.info(
                        f"[{method}] {view_name} - Status: {response.status_code}"
                    )
                elif response.status_code < 500:
                    logger.warning(
                        f"[{method}] {view_name} - Status: {response.status_code}"
                    )
                else:
                    logger.error(
                        f"[{method}] {view_name} - Status: {response.status_code}"
                    )

                return response

            except Exception as exc:
                logger.error(
                    f"[EXCEPTION] {view_name} - {type(exc).__name__}: {str(exc)}"
                )
                raise

        # Apply DRF's api_view decorator
        return api_view(http_method_names)(wrapped_view)

    return decorator
