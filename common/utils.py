from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
import logging

logger = logging.Logger('utils')


class APIResponse(Response):
    def __init__(self, data=None, meta=None, status=200, **kwargs):
        response_data = {'data': data}
        if meta:
            response_data['meta'] = meta

        super().__init__(response_data, status=status, **kwargs)


class APIError(Exception):
    def __init__(self, code, message, details=None):
        self.code = code
        self.message = message
        self.details = details or {}


def error_response(code, message, details=None, status_code=400):
    response_data = {
        "code": code,
        "message": message,
        "details": details
    }
    return APIResponse(data=None, status=status_code, **response_data)


class LoginMiddleWare(object):
    """ 拦截 JWT 验证 异常 ， 自定义返回数据格式 """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        logger.info(f"LoginMiddleWare: {request.path} - {response.status_code} - {response}")
        return response


class MyPagination(PageNumberPagination):
    page_size = 10  # 默认每一页 的数量
    page_size_query_param = 'pageSize'
    page_query_param = 'page'  # 参数 ?page=xx
    max_page_size = 15  # 最大指定每页个数
