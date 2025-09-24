"""Custom exception handling for the API."""
from __future__ import annotations

from typing import Any, Dict

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc: Exception, context: Dict[str, Any]) -> Response:
    """Return a structured error response with code/message/details."""
    response = exception_handler(exc, context)

    if response is None:
        return Response(
            {"code": "server_error", "message": str(exc), "details": {}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    payload = {
        "code": getattr(exc, "default_code", "error"),
        "message": getattr(exc, "detail", "An error occurred."),
        "details": response.data,
    }
    response.data = payload
    return response
