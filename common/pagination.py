from rest_framework.pagination import PageNumberPagination
from common.utils import APIResponse


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_query_param = 'page'
    page_size_query_param = 'size'  # 每页数量参数名

    def __init__(self):
        super().__init__()
        self.raw_page_size = None  # 新增字段保存原始参数值

    def get_page_size(self, request):
        """重写方法捕获原始size值"""
        self.raw_page_size = request.query_params.get(self.page_size_query_param)
        return super().get_page_size(request)

    def get_paginated_response(self, data):
        return APIResponse(
            data=data,
            meta={"pagination": {
                "total": self.page.paginator.count,
                "page": self.page.number,
                # "per_page": self.page_size
                "per_page": self._get_validated_page_size()
            }})

    def _get_validated_page_size(self):
        """校验并返回有效page_size"""
        try:
            # 尝试转换原始参数为整数
            return int(self.raw_page_size) if self.raw_page_size else self.page_size
        except (TypeError, ValueError):
            return self.page_size
