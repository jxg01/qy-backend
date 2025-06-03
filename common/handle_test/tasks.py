from celery import shared_task
from django.utils import timezone
import time
from common.handle_test.variable_pool import VariablePool
from common.handle_test.assertions import ASSERTION_MAPPING, extract_variables
from common.handle_test.request_executor import RequestExecutor

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy-backend.settings')
import django
django.setup()

from jk_case.models import TestExecution, SuiteCaseRelation, CaseExecution
from projects.models import GlobalVariable
from projects.projectsSerialize import GlobalVariableSerialize
# from celery.utils.log import get_task_logger
#
# log = get_task_logger(__name__)
import logging
import time

log = logging.getLogger('app')


@shared_task(bind=True, max_retries=3)
def async_execute_suite(self, execution_id):
    """异步执行测试套件任务"""
    # 获取执行记录
    vp = VariablePool()
    # 更新全局变量到内存
    get_global_variable = GlobalVariableSerialize(GlobalVariable.objects.all(), many=True)
    global_variable_list = {}
    for v in get_global_variable.data:
        global_variable_list[v['name']] = v['value']
    vp.update_global(global_variable_list)

    execution = TestExecution.objects.get(id=execution_id)
    try:
        # 更新状态为运行中
        execution.status = 'running'
        execution.started_at = timezone.now()
        execution.save()

        # 获取关联用例（按顺序且启用的用例）
        relations = SuiteCaseRelation.objects.filter(
            suite=execution.suite,
            case__enabled=True
        ).order_by('order').select_related('case')

        total = relations.count()
        # 用例通过数量，用于判断套件执行是否通过，和 total 对比
        passed = 0

        # 遍历执行每个用例
        for relation in relations:
            case = relation.case
            case_execution = CaseExecution.objects.create(
                execution=execution,
                case=case,
                status='pending',
            )

            try:
                # 发送请求并记录结果
                start_time = time.time()
                # 自定义请求接口需要的数据格式
                case_data = {
                    'method': case.interface.method,
                    'url': case.interface.project.base_url + case.interface.url,
                    'headers': case.interface.headers,
                    'body': case.body,
                }

                executor = RequestExecutor(vp)
                response = executor.execute(case_data)

                # 记录请求数据 - 提交过程会替换变量
                case_execution.request_data = case_data

                # 变量提取
                extracted = extract_variables(
                    case.variable_extract,
                    response
                )
                vp.extracted_vars.update(extracted)
                case_execution.extracted_vars = extracted

                # 记录执行时间
                duration = round(time.time() - start_time, 3)
                case_execution.duration = duration

                # 记录响应数据
                case_execution.response_data = {
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'body': response.json()
                }

                # 执行断言
                assertion_result = []
                default_assertion_status = 'success'
                for assertion in case.assertions:
                    # assert_type参数接收：
                    # [{"type": "status_code", "value": 200}, {'type': 'jsonpath_value', 'path': '$.status', 'expected': 200}]
                    assert_type = assertion['type']
                    assert_value = assertion['expected']
                    try:
                        assert_func = ASSERTION_MAPPING[assert_type]
                        assert_func(response, assert_value)
                        assertion_result.append({
                            'type': assert_type,
                            'status': 'success',
                            'expected': assert_value
                        })
                    except Exception as e:
                        assertion_result.append({
                            'type': assert_type,
                            'status': 'failed',
                            'expected': assert_value,
                            'actual': str(e)
                        })
                        default_assertion_status = 'failed'
                        break
                # 更新用例断言结果
                case_execution.assertions_result = assertion_result

                # 更新用例状态
                if default_assertion_status == 'success':
                    case_execution.status = 'passed'
                    passed += 1
                else:
                    case_execution.status = 'failed'
                case_execution.save()

            except Exception as e:
                # 记录用例级异常
                case_execution.status = 'failed'
                case_execution.response_data = {'error': str(e)}
                case_execution.duration = 0
                case_execution.save()

        # 更新整体执行状态
        execution.ended_at = timezone.now()
        execution.duration = (execution.ended_at - execution.started_at).total_seconds()
        execution.status = 'passed' if passed == total else 'failed'
        execution.save()

    except TestExecution.DoesNotExist:
        self.retry(countdown=60, max_retries=3)  # 重试3次，间隔60秒
    except Exception as e:
        # 处理任务级异常
        log.error(f'tasks ==== in exception Error => {str(e)}')
        execution.status = 'failed'
        execution.ended_at = timezone.now()
        execution.save()
        log.info('end exception!!! ')
        self.retry(exc=e, countdown=60, max_retries=3)


# if __name__ == '__main__':
#     async_execute_suite.delay(1)
#     # Example usage
#     vp = VariablePool()
#     executor = RequestExecutor(vp)
#
#     get_global_variable = GlobalVariableSerialize(GlobalVariable.objects.all(), many=True)
#     print('data => ', get_global_variable.data)
#     global_variable_list = {}
#     for v in get_global_variable.data:
#         global_variable_list[v['name']] = v['value']
#     vp.update_global(global_variable_list)
#     print(vp.global_vars)
#
#     case_data1 = {
#         'method': 'POST',
#         'url': 'http://localhost:8000/api/users/',
#         'headers': {'Authorization': 'Bearer ${token}', 'accept': 'application/json'},
#         'body': {'data': {'page': '${suite.page}', 'per_page': '${per_page}', 'order_id': '${global.order_id}'}, 'type': 'formdata'},
#     }
#
#     vp.update_extracted({'id': 333, 'page': 1, 'per_page': '1220', 'token': '123'})
#     i = case_data1['body'].get('data')
#     print('i => ', i)
#     bb = {
#         k: vp.parse_placeholder(v)
#         for k, v in case_data1['body'].get('data', []).items()
#     }
#     print('zh => ', bb)
#     # response = executor.execute(case_data1)
#     # print(response.status_code, response.text)

