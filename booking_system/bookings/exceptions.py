import logging

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Centralised exception handler — returns a consistent JSON envelope
    and never leaks raw Python tracebacks to the client.
    """
    response = exception_handler(exc, context)

    if response is not None:
        # Normalise the DRF error payload
        detail = response.data
        if isinstance(detail, dict) and 'detail' in detail:
            message = str(detail['detail'])
        elif isinstance(detail, list):
            message = '; '.join(str(e) for e in detail)
        elif isinstance(detail, dict):
            parts = []
            for field, errors in detail.items():
                if isinstance(errors, list):
                    parts.append(f"{field}: {'; '.join(str(e) for e in errors)}")
                else:
                    parts.append(f"{field}: {errors}")
            message = ' | '.join(parts)
        else:
            message = str(detail)

        response.data = {
            'success': False,
            'message': message,
        }
        return response

    # Unhandled exception — log it and return a safe 500
    logger.exception('Unhandled server error in %s', context.get('view'))
    return Response(
        {'success': False, 'message': 'An unexpected error occurred.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
