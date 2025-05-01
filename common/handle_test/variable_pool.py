import re


class VariablePool:
    def __init__(self):
        self.global_vars = {}
        self.suite_vars = {}
        self.extracted_vars = {}

    def update_global(self, data: dict):
        self.global_vars.update(data)

    def update_suite(self, data: dict):
        self.suite_vars.update(data)

    def update_extracted(self, data: dict):
        self.suite_vars.update(data)

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

    def parse_placeholder(self, raw_str: str):
        """解析${variable}格式的占位符"""
        pattern = r"\${([\w\.]+)}"
        return re.sub(pattern, lambda m: str(self.get_value(m.group(1))), raw_str)
