from enum import Enum
from typing import Dict, Any

# class ErrorCode:
#     SUCCESS = 0
#     PARAM_ERROR = 1001
#     UNIQUE_CONSTRAINT = 1002
#     SERVER_ERROR = 1999
#     # 登录
#     AUTH_ERROR = 2001
#     USER_NOT_EXIST = 2002
#     WRONG_PASSWORD = 2003
#     # 用户
#     USERNAME_EXISTS = 3001
#     EMAIL_EXISTS = 3002
#     OPERATION_NOT_ALLOWED = 3003
#     USER_NOT_FOUND = 3004
#     # 项目
#     PROJECT_EXISTS = 4001


class ErrorCode(Enum):
    """错误码枚举（唯一数据源）"""
    # 公共字段校验
    PARAM_ERROR = (99, "参数校验失败")
    DATA_NOT_EXISTS = (101, "数据不存在")
    # 登录
    USER_NOT_EXISTS = (901, "用户名不存在")
    PASSWORD_ERROR = (902, "密码错误")

    # 注册
    PASSWORD_DIFFERENT = (911, "两次密码输入不正确")
    REGISTER_USER_EXISTS = (912, "用户已存在")
    REGISTER_EMAIL_EXISTS = (913, "邮箱已存在")
    # users
    USERNAME_EXISTS = (1001, "用户名称不能重复")
    EMAIL_EXISTS = (1002, "邮箱不能重复")
    DELETE_CURRENT_USER = (1003, "不能删除当前登录用户")
    # projects
    PROJECT_NAME_EXISTS = (2001, "项目名称不能重复")

    # variable
    VARIABLE_NAME_EXISTS = (3001, "变量名称不能重复")

    # 后续新增错误码只需在此添加

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


# class ErrorRegistry:
#     """错误码映射注册器"""
#     _field_error_map: Dict[str, ErrorCode] = {
#         'username': ErrorCode.USERNAME_EXISTS,
#         'name': ErrorCode.PROJECT_NAME_EXISTS
#     }
#
#     @classmethod
#     def get_error_by_field(cls, field: str) -> ErrorCode:
#         """通过字段名获取预设错误码"""
#         return cls._field_error_map.get(field)

