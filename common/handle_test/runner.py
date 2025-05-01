from request_executor import RequestExecutor
from common.handle_test.variable_pool import VariablePool
from common.handle_test.assertions import ASSERTION_MAPPING
from apps.jk_case.models import TestSuite
import jsonpath
import time


class TestRunner:
    def __init__(self, suite_id):
        self.suite = TestSuite.objects.get(id=suite_id)
        self.variable_pool = VariablePool()
        self.executor = RequestExecutor(self.variable_pool)
        self.results = []

    def _extract_variables(self, extract_rules, response):
        """使用JSONPath提取变量
        example:
            extract_rules = [
                {"name": "user_id", "path": "$.data.user.id"},
                {"name": "token", "path": "$.data.token"}
            ]
        """
        extracted = {}
        for rule in extract_rules:
            values = jsonpath.jsonpath(response.json(), rule['path'])
            if values:
                extracted[rule['name']] = values[0]
        return extracted

    def _run_case(self, case):
        start_time = time.time()
        result = {
            'case_id': case.id,
            'request': case.request_data,
            'response': None,
            'assertions': [],
            'variables': {},
            'status': 'success'
        }

        try:
            # 执行请求
            response = self.executor.execute(case.request_data)
            result['response'] = {
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'body': response.text
            }

            # 变量提取
            extracted = self._extract_variables(
                case.request_data.get('extract', []),
                response
            )
            self.variable_pool.extracted_vars.update(extracted)
            result['variables'] = extracted

            # 执行断言
            for assertion in case.request_data.get('assertions', []):
                # assert_type参数接收：
                # [{'type': 'status_code', 'value': 200}, {'type': 'jsonpath', 'path': '$.status', 'expected': 200}]
                assert_type = assertion['type']
                assert_value = assertion['value']
                try:
                    assert_func = ASSERTION_MAPPING[assert_type]
                    assert_func(response, assert_value)
                    result['assertions'].append({
                        'type': assert_type,
                        'status': 'success',
                        'expected': assert_value
                    })
                except Exception as e:
                    result['assertions'].append({
                        'type': assert_type,
                        'status': 'failed',
                        'expected': assert_value,
                        'actual': str(e)
                    })
                    result['status'] = 'failed'
                    break

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)

        result['duration'] = time.time() - start_time
        return result

    def execute_suite(self):
        ordered_cases = SuiteService.get_ordered_cases(self.suite.id)
        for case in ordered_cases:
            case_result = self._run_case(case)
            self.results.append(case_result)
            ExecutionResult.objects.create(
                case=case,
                suite=self.suite,
                status=case_result['status'],
                request_data=case_result['request'],
                response_data=case_result.get('response'),
                assertions=case_result['assertions'],
                variables=case_result['variables'],
                duration=case_result['duration']
            )
        return self.results
