import json
import requests
from variable_pool import VariablePool


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
                for k, v in case_data['body'].items()
            }
        else:
            # 处理不同参数类型
            if case_data['content_type'] == 'json':
                processed_data['json'] = json.loads(
                    self.variable_pool.parse_placeholder(
                        json.dumps(case_data['body'])
                    )
                )
            elif case_data['content_type'] == 'formdata':
                processed_data['data'] = {
                    k: self.variable_pool.parse_placeholder(v)
                    for k, v in case_data['body'].items()
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
        'url': 'https://staff-tmgm-cn-2-qa.lifebyte.dev/api/funding/transactions/getWithdrawalFileList/${id}',
        'headers': {'Authorization': 'Bearer ${token}', 'accept': 'application/prs.CRM-Back-End.v3+json'},
        'body': {'page': '${page}', 'per_page': '${per_page}'},
        'content_type': 'formdata'
    }

    vp.update_extracted({'id': 333, 'page': 1, 'per_page': '10', 'token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxIiwianRpIjoiZWMzOGM1M2YwNTE1NjhiYmU4ZjFjYWFkMTU4NGU5NzM4MTliZTFiOGVkNDk4ZWU3ZjFmMzRmNDc5OTcwMTBlOGY0Zjg0M2U1YTk1ZDI4ZTciLCJpYXQiOjE3NDU4OTQ2MzQsIm5iZiI6MTc0NTg5NDYzNCwiZXhwIjoxNzQ1OTgxMDM0LCJzdWIiOiIyNjYiLCJzY29wZXMiOlsiKiJdfQ.rwneKy34jErCa3_lS5QVkI_40jSmwNAaS4Q-UJRZgRFZGagbozIwKV69SpHPQ409iafl2LbVrlq84Tecj9mRSa2Lfu5i47J745HdGkk2BFsrXcKAEyUYS30iIh6K4yrvl58mIp908YHhZhCccYSUf-gyGHfhT8WaG-TVMmZW4dnFNjOPlwG0s6dVbK8bHfR-Xco6LXE810syRZQHNrcT5yLoVGb_60P4Psg5MXLhYITCl9C7jJxdPW37Lrve-wBCQp6f0A2gD8-H5ZCxSyyWXNMrNd_HxgFbLR_pzyqtLFpMhrf3OH4MuLYRmgWx0PZnrJ-6e8BFhKoWgV_34SrjT8QqNn_6Aak5XsgS3Eg9s78sw_ftOflsx0lP1vS9fQNuMm7AqZIB-4ymRGtdky0eZz0Sd4e2EnA-TNtVab_3HbBr8X49MCAGg4ks1AyVZiDZA3TNpswXQnxfpOF3ygf2qI-oTGs88-ocyg1NEp15VrTQiVrgLGz_63vSwEYWLXs32020cVU8BSfjUghBcK-wNdCOnROCwAXHE2sFJDuqF400DdiJX5jBgR7s9NYtGbjmC_9zzDBzHVVq7hvjqbqssUjNrYsB_Tuj67M9TItJ71teVaaTushrfexO33OY_0N5MVF4UW9S-J506nBlzYmIo7pUOkkoFUBnmSnKbxrsA3g'})
    response = executor.execute(case_data1)
    print(response.status_code, response.text)
