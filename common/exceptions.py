from rest_framework.views import exception_handler
from rest_framework import status, serializers
from rest_framework.exceptions import APIException, NotAuthenticated
from rest_framework_simplejwt.exceptions import InvalidToken
from common.error_codes import ErrorCode
from django.http.response import Http404
import re
import logging

log = logging.getLogger('django')


class BusinessException(APIException):
    """通用业务异常（通过 ErrorCode 生成）"""
    status_code = status.HTTP_200_OK

    def __init__(self, error_code: ErrorCode, extra_data=None):
        self.code = error_code.code
        self.message = error_code.message
        self.extra_data = extra_data  # 可携带额外数据
        r_data = {
                'code': self.code,
                'message': self.message,
                # 'data': self.extra_data
            }
        if self.extra_data:
            r_data['data'] = self.extra_data

        super().__init__(detail=r_data)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    response.status_code = status.HTTP_200_OK
    log.info(f'response => {response} ')
    log.info(f'response type => {type(exc)}')

    if isinstance(exc, NotAuthenticated):
        response.status_code = status.HTTP_401_UNAUTHORIZED
        response.data = {
            'code': ErrorCode.UN_AUTHORIZED.code,
            'message': ErrorCode.UN_AUTHORIZED.message,
        }
        return response

    if isinstance(exc, InvalidToken):
        response.status_code = status.HTTP_401_UNAUTHORIZED
        response.data = {
            'code': ErrorCode.UN_AUTHORIZED.code,
            'message': ErrorCode.UN_AUTHORIZED.message,
        }
        return response

    # 处理通用业务异常
    if isinstance(exc, BusinessException):
        return response  # 异常类已包含格式化数据

    # 自动处理数据库唯一性错误
    # if isinstance(exc, IntegrityError):
    #     field = _parse_unique_field(str(exc))  # 解析字段名
    #     if error_code := ErrorRegistry.get_error_by_field(field):
    #         return BusinessException(error_code).get_response()
    if isinstance(exc, serializers.ValidationError):
        errors = {}
        for field, messages in exc.detail.items():
            errors[field] = [str(msg) for msg in messages]
        response.data = {
            'code': ErrorCode.PARAM_ERROR.code,
            'message': ErrorCode.PARAM_ERROR.message,
            'errors': errors
        }
    if isinstance(exc, Http404):
        response.data = {
            'code': ErrorCode.DATA_NOT_EXISTS.code,
            'message': ErrorCode.DATA_NOT_EXISTS.message,
        }
    # 其他异常处理逻辑...
    return response
