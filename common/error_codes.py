from enum import Enum


class ErrorCode(Enum):
    """错误码枚举（唯一数据源）"""
    UN_AUTHORIZED = (1, "认证失败，请提供有效凭证")
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
    OLD_PASSWORD_ERROR = (1004, "旧密码错误")
    INVALID_PARAMS = (1005, "无效参数")
    PASSWORD_SAME = (1006, "新密码不能与旧密码相同")
    # projects
    PROJECT_NAME_EXISTS = (2001, "项目名称不能重复")

    # variable
    VARIABLE_NAME_EXISTS = (3001, "变量名称不能重复")

    # 用例
    TESTCASE_DISABLED = (4001, "用例已经被禁用")

    # 套件
    SUITE_RELATED_CASE_NOT_EXISTS = (5001, "套件下没有关联用例")
    SUITE_RELATED_CASE_ALL_DISABLED = (5002, "套件下所有用例都已被禁用")

    # UI 元素
    UI_ELEMENT_NAME_EXISTS = (6001, "元素名称不能重复")
    UI_ELEMENT_NAME_EMPTY = (6002, "元素名称不能为空")
    UI_ELEMENT_LOCATOR_EXISTS = (6003, "定位值已存在")
    UI_ELEMENT_LOCATOR_VALUE_EMPTY = (6004, "定位值不能为空")
    UI_TESTCASE_NAME_EXISTS = (6005, "用例名称不能重复")
    UI_TESTCASE_NAME_EMPTY = (6006, "用例名称不能为空")
    PROJECT_IS_EMPTY = (6007, "项目不能为空")
    DB_NOT_EXISTS = (6008, "数据库未配置，请检查默认环境的数据库信息")
    SELECTED_CASES_ID_IS_EMPTY = (6008, "用例ID不能为空")

    # cron
    CRON_ERROR = (7001, "Cron 表达式格式错误")

    # 后续新增错误码只需在此添加

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
