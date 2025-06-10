import json
import requests
from common.handle_test.variable_pool import VariablePool
import logging

log = logging.getLogger('django')


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
                for k, v in case_data['params'].items()
            }
        else:
            if case_data['body_type'] == 'form':
                processed_data['data'] = {
                    k: self.variable_pool.parse_placeholder(v)
                    for k, v in case_data['data'].items()
                }
            else:
                processed_data['json'] = json.loads(
                    self.variable_pool.parse_placeholder(case_data['body'])
                )
        return processed_data

    def execute(self, case_data: dict):
        prepared = self.prepare_request(case_data)
        log.info(f'Executing request with data: {prepared}', )
        return self.session.request(**prepared), prepared


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
