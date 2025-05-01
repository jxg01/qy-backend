from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
import logging
from django.conf import settings

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
    # 开发环境添加堆栈信息
    # if settings.DEBUG:
    #     import traceback
    #     response_data['details']['stack'] = traceback.format_stack()
    return APIResponse(data=None, status=status_code, **response_data)





# class ReMsg:
#     def __init__(self, code=0, msg='成功', data=None):
#         self.code = code
#         self.msg = msg
#         self.data = {} if data is None else data
#
#     def res_msg(self):
#         return {
#             'code': self.code,
#             'message': self.msg,
#             'data': self.data
#         }
#
#
# class CustomModelViewSet(ModelViewSet):
#     def create(self, request, *args, **kwargs):
#         response = super().create(request, *args, **kwargs)
#         return Response(ReMsg(data=response.data).res_msg(), status=response.status_code)
#
#     def list(self, request, *args, **kwargs):
#         response = super().list(request, *args, **kwargs)
#         return Response(ReMsg(data=response.data).res_msg(), status=response.status_code)
#
#     def retrieve(self, request, *args, **kwargs):
#         response = super().retrieve(request, *args, **kwargs)
#         return Response(ReMsg(data=response.data).res_msg(), status=response.status_code)
#
#     def update(self, request, *args, **kwargs):
#         response = super().update(request, *args, **kwargs)
#         return Response(ReMsg(data=response.data).res_msg(), status=response.status_code)
#
#     def destroy(self, request, *args, **kwargs):
#         response = super().destroy(request, *args, **kwargs)
#         return Response(ReMsg(data=response.data).res_msg(), status=response.status_code)
#
#
# class CustomMixin(UpdateModelMixin, ListModelMixin, CreateModelMixin, DestroyModelMixin, RetrieveModelMixin):
#     def update(self, request, *args, **kwargs):
#         partial = kwargs.pop('partial', False)
#         instance = self.get_object()
#         serializer = self.get_serializer(instance, data=request.data, partial=partial)
#         serializer.is_valid(raise_exception=True)
#         self.perform_update(serializer)
#
#         if getattr(instance, '_prefetched_objects_cache', None):
#             # If 'prefetch_related' has been applied to a queryset, we need to
#             # forcibly invalidate the prefetch cache on the instance.
#             instance._prefetched_objects_cache = {}
#
#         # return Response(serializer.data)
#         d = {
#             'code': 0,
#             'message': '修改成功',
#             'data': None
#         }
#         return Response(d)
#
#     def list(self, request, *args, **kwargs):
#         queryset = self.filter_queryset(self.get_queryset())
#
#         page = self.paginate_queryset(queryset)
#         if page is not None:
#             serializer = self.get_serializer(page, many=True)
#             return self.get_paginated_response(serializer.data)
#
#         serializer = self.get_serializer(queryset, many=True)
#         print('serializer.data', serializer.data)
#         d = {
#             'code': 0,
#             'message': '成功',
#             'data': serializer.data
#         }
#         return Response(d)
#
#     def create(self, request, *args, **kwargs):
#         print('request.data === ', request.data)
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         self.perform_create(serializer)
#         headers = self.get_success_headers(serializer.data)
#         dt = {
#             'code': 0,
#             'message': '添加成功',
#             'data': None
#         }
#         return Response(dt)
#
#     def retrieve(self, request, *args, **kwargs):
#         instance = self.get_object()
#         serializer = self.get_serializer(instance)
#         d = {
#             'code': 0,
#             'message': '修改成功',
#             'data': None
#         }
#         return Response(d)
#
#     def destroy(self, request, *args, **kwargs):
#         instance = self.get_object()
#         self.perform_destroy(instance)
#         d = {
#             'code': 0,
#             'message': '删除成功',
#             'data': None
#         }
#         return Response(d, status=Response.status_code)
#
#     def perform_destroy(self, instance):
#         instance.delete()
#
#
# def set_rollback():
#     atomic_requests = connection.settings_dict.get('ATOMIC_REQUESTS', False)
#     if atomic_requests and connection.in_atomic_block:
#         transaction.set_rollback(True)
#
#
# def exception_handler(exc, context):
#     """ 重写django全局错误返回信息格式 """
#     if isinstance(exc, Http404):
#         exc = exceptions.NotFound()
#     elif isinstance(exc, PermissionDenied):
#         exc = exceptions.PermissionDenied()
#
#     if isinstance(exc, exceptions.APIException):
#         headers = {}
#         if getattr(exc, 'auth_header', None):
#             headers['WWW-Authenticate'] = exc.auth_header
#         if getattr(exc, 'wait', None):
#             headers['Retry-After'] = '%d' % exc.wait
#         if isinstance(exc.detail, (list, dict)):
#             if isinstance(exc.detail, list):
#                 error = exc.detail
#             else:
#                 # error = {k: v[0] for k, v in exc.detail.items()}
#                 error = ''
#                 for k, v in exc.detail.items():
#                     error = v[0]
#         else:
#             error = exc.detail
#
#         set_rollback()
#         return Response({'code': 1000, 'message': '失败', 'error': str(error)}, status=Response.status_code, headers=headers)
#
#     return None
#
#
# def jwt_response_payload_handler(token, user=None, request=None):
#     """
#     自定义jwt认证成功返回数据
#     :token  返回的jwt
#     :user   当前登录的用户信息[对象]
#     :request 当前本次客户端提交过来的数据
#     """
#     return {
#         'code': 0,
#         'message': '成功',
#         'data': {
#             'id': user.id,
#             'username': user.username,
#             'token': token,
#         }
#     }
#
#
# def jwt_response_payload_error_handler(serializer, request=None):
#     results = {
#         "code": 1,
#         "message": "失败",
#         "error": serializer.errors
#     }
#     print('serializer.errors', serializer.errors)
#     e = serializer.errors
#     if isinstance(e, dict):
#         print('test')
#         print(e.values())
#         results['error'] = str(e.values()).split("'")[1]
#         return results
#     else:
#         return results
#
#
class LoginMiddleWare(object):
    """ 拦截 JWT 验证 异常 ， 自定义返回数据格式 """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    # def process_template_response(self, request, response):
    #     if hasattr(response, 'data'):
    #         print(response.data)
    #         if response.status_code == 404:
    #             print(response.status_code)
    #             response.data['error'] = '数据不存在'
    #         elif response.status_code == 401:
    #             print(response.status_code)
    #             response.data['error'] = '未登录，请先登录'
    #     return response


class MyPagination(PageNumberPagination):
    page_size = 10  # 默认每一页 的数量
    page_size_query_param = 'pageSize'
    page_query_param = 'page'  # 参数 ?page=xx
    max_page_size = 15  # 最大指定每页个数


