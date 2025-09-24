"""API pagination utilities."""
from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Consistent pagination used across all endpoints."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
