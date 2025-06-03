import json

import jsonpath


def status_code(response, expected):
    """断言响应状态码"""
    assert response.status_code == int(expected['expected']), f"Expected {expected['expected']}, but got {response.status_code}"


def jsonpath_exist(response, expected):
    """断言JSONPath存在"""
    json_data = response.json()
    assert jsonpath.jsonpath(json_data, expected), f"Expected {expected}, but got {json_data}"


def jsonpath_equal(response, expected):
    """断言响应体"""
    actual_value = jsonpath.jsonpath(response.json(), expected['path'])
    if actual_value:
        actual_value = actual_value[0]
        assert actual_value == expected['expected'], f"Expected {expected['expected']}, but got {actual_value}"
    else:
        assert False, f"JSONPath {expected['path']} not found in response"


def value_in_response(response,  expected):
    """断言响应体"""
    assert expected in response.text, f"Expected {expected} not in Response!"


ASSERTION_MAPPING = {
    'status_code': status_code,
    'jsonpath_exist': jsonpath_exist,
    'jsonpath_equal': jsonpath_equal,
    'value_in_response': value_in_response
}


def extract_variables(extract_rules, response):
    """使用JSONPath提取变量
    example:
        extract_rules = [
            {"name": "user_id", "path": "$.data.user.id"},
            {"name": "token", "path": "$.data.token"}
        ]
    """
    extracted = {}
    for rule in extract_rules:
        if rule:
            values = jsonpath.jsonpath(response.json(), rule['path'])
            if values:
                extracted[rule['name']] = values[0]
            else:
                extracted[rule['name']] = ''
    return extracted

