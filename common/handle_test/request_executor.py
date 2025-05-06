import json
import requests
from common.handle_test.variable_pool import VariablePool
import logging

log = logging.getLogger('app')


class RequestExecutor:
    def __init__(self, variable_pool):
        self.session = requests.Session()
        self.variable_pool = variable_pool

    def prepare_request(self, case_data: dict):
        """处理请求参数和变量替换"""
        processed_data = {
            'method': case_data['method'],
            'url': self.variable_pool.parse_placeholder(case_data['url']),
            'headers': json.loads(
                self.variable_pool.parse_placeholder(
                    json.dumps(case_data['headers'])
                )
            )
        }
        if case_data['method'] == 'GET':
            processed_data['params'] = {
                k: self.variable_pool.parse_placeholder(v)
                for k, v in case_data['body'].get('data', []).items()
            }
        else:
            # 处理不同参数类型
            if case_data['body'].get('type') == 'json':
                processed_data['json'] = json.loads(
                    self.variable_pool.parse_placeholder(
                        json.dumps(case_data['body'].get('data', []))
                    )
                )
            elif case_data['body'].get('type') == 'formdata':
                processed_data['data'] = {
                    k: self.variable_pool.parse_placeholder(v)
                    for k, v in case_data['body'].get('data', []).items()
                }
        return processed_data

    def execute(self, case_data: dict):
        prepared = self.prepare_request(case_data)
        return self.session.request(**prepared)


if __name__ == '__main__':
    # Example usage
    vp = VariablePool()
    executor = RequestExecutor(vp)

    case_data1 = {
        'method': 'POST',
        'url': 'http://localhost:8000/api/users/',
        'headers': {'Authorization': 'Bearer ${token}', 'accept': 'application/json'},
        'body': {'data': {'page': '${page}', 'per_page': '${per_page}'}, 'type': 'formdata'},
    }

    vp.update_extracted({'id': 333, 'page': 1, 'per_page': '1220', 'token': '123'})
    response = executor.execute(case_data1)
    print(response.status_code, response.text)
