import math
import logging
from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class TMSBasePagination(CursorPagination):

    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate the queryset and store the list of IDs for later use in the response.
        """
        self.id_list = list(queryset.values_list('pk', flat=True))  # Extract IDs before pagination
        logger.debug(f"paginate_queryset: id_list: {self.id_list}")
        return super().paginate_queryset(queryset, request, view)


    def get_paginated_response(self, data):
        """
        Add the id_list to the response.
        """
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'id_list': self.id_list,  # Include extracted IDs
            'results': data
        })


class LoadPagination(PageNumberPagination):
    page_size = 45
    page_size_query_param = 'page_size'
    max_page_size = 45

    def get_paginated_response(self, data):
        start_index = (self.page.number - 1) * self.page.paginator.per_page + 1
        end_index = start_index + len(data) - 1
        return Response({
            'current_page_range': f"{start_index}-{end_index}",
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'total_pages': math.ceil(self.page.paginator.count / self.page.paginator.per_page),
            'results': data
        })


class AddressPagination(TMSBasePagination):
    page_size = 18
    page_size_query_param = 'page'
    ordering = 'place_name'


class EntityPagination(TMSBasePagination):
    page_size = 18
    page_size_query_param = 'page'
    ordering = 'company_name'
