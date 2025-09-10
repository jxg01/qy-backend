from typing import Any, Iterable, Optional
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from common.utils import APIResponse

class StandardPagination(PageNumberPagination):
    page_query_param = 'page'
    page_size_query_param = 'size'
    page_size = 20
    max_page_size = 200
    last_page_strings = ('last',)

    def __init__(self) -> None:
        super().__init__()
        self.raw_page_size: Optional[str] = None

    def get_page_size(self, request: Request) -> Optional[int]:
        self.raw_page_size = request.query_params.get(self.page_size_query_param)
        return super().get_page_size(request)

    def get_page_number(self, request: Request, paginator) -> int:
        raw = request.query_params.get(self.page_query_param, 1)
        if isinstance(raw, str) and raw.lower() in self.last_page_strings:
            return max(1, getattr(paginator, 'num_pages', 1) or 1)
        try:
            number = int(raw)
        except (TypeError, ValueError):
            number = 1
        if number < 1:
            number = 1
        num_pages = getattr(paginator, 'num_pages', 1) or 1
        if number > num_pages:
            number = num_pages
        return number

    def paginate_queryset(self, queryset, request: Request, view=None) -> Optional[Iterable[Any]]:
        self.request = request
        page_size = self.get_page_size(request)
        if not page_size:
            return None
        paginator = self.django_paginator_class(queryset, page_size)
        page_number = self.get_page_number(request, paginator)
        self.page = paginator.page(page_number)
        self.page_size = page_size
        if paginator.num_pages > 1 and self.template is not None:
            self.display_page_controls = True
        return list(self.page)

    def get_paginated_response(self, data) -> Response:
        return APIResponse(
            data=data,
            meta={
                "pagination": {
                    "total": self.page.paginator.count,
                    "page": self.page.number,
                    "per_page": self._get_validated_page_size(),
                    "pages": self.page.paginator.num_pages,
                    "has_next": self.page.has_next(),
                    "has_prev": self.page.has_previous(),
                }
            },
        )

    def _get_validated_page_size(self) -> int:
        try:
            return int(self.raw_page_size) if self.raw_page_size else int(self.page_size)
        except (TypeError, ValueError):
            return int(self.page_size)
