from celery import shared_task
from django.utils import timezone
from common.handle_test.variable_pool import VariablePool
from common.handle_test.assertions import ASSERTION_MAPPING, extract_variables
from common.handle_test.request_executor import RequestExecutor

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy_backend.settings')
import django
django.setup()

from jk_case.models import TestExecution, SuiteCaseRelation, CaseExecution
from projects.models import GlobalVariable, PythonCode
import time
# 异步任务中显式接收 User object
from django.contrib.auth import get_user_model
import logging

log = logging.getLogger('celery.task')


@shared_task(bind=True, max_retries=3)
def async_execute_suite(self, execution_id, executed_by, env_url):
    """异步执行测试套件任务"""
    # 获取任务记录器
    user = get_user_model().objects.get(id=executed_by)
    log.info(f"🚀 开始执行测试套件任务: execution_id={execution_id}, executed_by={user.username}, env_url={env_url}")

    # 获取执行记录
    vp = VariablePool()
    # 更新全局变量到内存
    global_vars = GlobalVariable.objects.values_list('name', 'value')
    vp.update_global({name: value for name, value in global_vars})

    # 更新Python代码
    python_codes = PythonCode.objects.all()
    if python_codes:
        vp.set_function_code(python_codes[0].python_code)


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
            log.info(f"正在执行用例: {case.name} (ID: {case.id})")
            case_execution = CaseExecution.objects.create(
                execution=execution,
                case=case,
                status='pending',
                executed_by=user
            )

            try:
                # 发送请求并记录结果
                start_time = time.time()
                # 自定义请求接口需要的数据格式
                case_data = {
                    'method': case.interface.method,
                    'url': env_url + case.interface.path,
                    'headers': case.headers or {},
                    'body': case.body,
                    'params': case.params,
                    'data': case.data,
                    'body_type': case.body_type
                }

                executor = RequestExecutor(vp)
                response, actual_reqeust_data = executor.execute(case_data)

                # 记录请求数据（变量替换后）
                case_execution.request_data = actual_reqeust_data

                # 变量提取
                extracted = extract_variables(
                    case.variable_extract,
                    response
                )
                vp.suite_vars.update(extracted)
                case_execution.extracted_vars = extracted

                # 记录执行时间
                duration = round(time.time() - start_time, 3)
                case_execution.duration = duration

                # 记录响应数据
                case_execution.response_data = {
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'body': response.text
                }

                # 执行断言
                assertion_result = []
                all_passed = True
                for assertion in case.assertions:
                    if not assertion:
                        continue
                    # assert_type参数接收：
                    # [{"type": "status_code", "value": 200}, {'type': 'jsonpath_value', 'path': '$.status', 'expected': 200}]
                    assert_type = assertion['type']
                    assert_value = assertion['expected']
                    try:
                        assert_func = ASSERTION_MAPPING[assert_type]
                        assert_func(response, assertion)
                        assertion_result.append({
                            'type': assert_type,
                            'status': 'success',
                            'expected': assert_value,
                            'actual': assert_value
                        })
                    except Exception as e:
                        assertion_result.append({
                            'type': assert_type,
                            'status': 'failed',
                            'expected': assert_value,
                            'actual': str(e)
                        })
                        all_passed = False
                        break
                # 更新用例断言结果
                case_execution.assertions_result = assertion_result

                # 更新用例状态
                if all_passed:
                    case_execution.status = 'passed'
                    passed += 1
                else:
                    case_execution.status = 'failed'
                case_execution.save()

            except Exception as e:
                # 记录用例级异常
                case_execution.status = 'failed'
                case_execution.response_data = {'error': str(e)}
                case_execution.duration = round(time.time() - start_time, 3)
                case_execution.save()

        # 更新整体执行状态
        execution.ended_at = timezone.now()
        execution.duration = (execution.ended_at - execution.started_at).total_seconds()
        execution.status = 'passed' if passed == total else 'failed'
        execution.save()
        log.info('Task End Success!!! ')

    except TestExecution.DoesNotExist:
        self.retry(countdown=60, max_retries=3)  # 重试3次，间隔60秒
    except Exception as e:
        # 处理任务级异常
        log.error(f'Tasks Error => {str(e)}')
        execution.status = 'failed'
        execution.ended_at = timezone.now()
        execution.save()
        log.info('Task End Exception!!! ')
        self.retry(exc=e, countdown=60, max_retries=3)


# if __name__ == '__main__':
#     async_execute_suite.delay(1, 'http://127.0.0.1:8000' , 1)
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

