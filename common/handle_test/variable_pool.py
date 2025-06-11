import re
import logging
import ast

log = logging.getLogger('django')


class VariablePool:
    def __init__(self):
        self.global_vars = {}
        self.suite_vars = {}
        self.extracted_vars = {}
        self.function_code = ""  # 存储函数代码字符串

    def set_function_code(self, code_str: str):
        """设置包含可执行函数的代码字符串"""
        self.function_code = code_str

    def update_global(self, data: dict):
        self.global_vars.update(data)

    def update_suite(self, data: dict):
        self.suite_vars.update(data)

    def update_extracted(self, data: dict):
        self.extracted_vars.update(data)

    def get_value(self, key: str):
        # 支持作用域前缀解析
        if '.' in key:
            scope, name = key.split('.', 1)
            if scope == 'suite':
                return self.suite_vars.get(name)
            elif scope == 'global':
                return self.global_vars.get(name)
            elif scope == 'case':
                return self.extracted_vars.get(name)
        # 默认优先级逻辑，如果没有传入作用域前缀，则按顺序查找 ｜ ${username}
        return self.extracted_vars.get(key) or self.suite_vars.get(key) or self.global_vars.get(key)

    def parse_arguments(self, arg_str: str):
        """解析参数字符串为Python对象列表"""
        if not arg_str:
            return []

        try:
            # 安全解析参数列表
            return ast.literal_eval(f'[{arg_str}]')
        except (SyntaxError, ValueError):
            # 处理无引号的字符串参数
            return [arg.strip() for arg in arg_str.split(',')]

    def execute_function(self, func_name: str, *args):
        """执行指定函数并返回结果"""
        if not self.function_code:
            raise ValueError("未设置函数代码")

        namespace = {}
        try:
            exec(self.function_code, namespace)
            func = namespace.get(func_name)
            if not func:
                raise ValueError(f"函数 {func_name} 未找到")
            return func(*args)
        except Exception as e:
            log.error(f"执行函数 {func_name} 失败: {str(e)}")
            raise

    def parse_placeholder(self, raw_str: str):
        """解析所有类型的占位符，包括变量和函数调用"""
        # 先处理函数调用占位符
        func_pattern = r'\${__(\w+)\((.*?)\)}'

        def func_replacement(match):
            func_name = match.group(1)
            arg_str = match.group(2).strip()

            # 解析参数
            args = self.parse_arguments(arg_str) if arg_str else []

            try:
                # 执行函数
                func_result = self.execute_function(func_name, *args)
                return str(func_result)
            except Exception as e:
                log.error('执行函数失败: %s', str(e))
                # 执行失败时返回原始占位符
                return match.group(0)

        # 替换函数调用
        result = re.sub(func_pattern, func_replacement, raw_str)

        # 再处理变量占位符
        var_pattern = r'\${([\w\.]+)}'

        def var_replacement(match):
            var_name = match.group(1)
            value = self.get_value(var_name)
            # 未找到变量值时返回原始占位符
            return str(value) if value is not None else match.group(0)

        result = re.sub(var_pattern, var_replacement, result)

        log.info(f'解析占位符: {raw_str} -> {result}')
        return result
