from common.handle_test.variable_pool import VariablePool
from common.handle_test.assertions import ASSERTION_MAPPING, extract_variables
from common.handle_test.request_executor import RequestExecutor

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy-backend.settings')
import django
django.setup()

from jk_case.models import CaseExecution
from projects.models import GlobalVariable, PythonCode
import logging
import time

log = logging.getLogger('django')


def execute_case(case_obj, execute_env, executed_by):
    """异步执行单个测试用例任务"""
    log.info('🚀 开始执行测试用例')
    # 初始化变量池
    vp = VariablePool()
    case_execution = CaseExecution.objects.create(
        case=case_obj,
        status='pending',
        executed_by=executed_by
    )
    try:
        # 更新全局变量
        global_vars = GlobalVariable.objects.values_list('name', 'value')
        vp.update_global({name: value for name, value in global_vars})

        # 更新Python代码
        python_codes = PythonCode.objects.all()
        if python_codes:
            vp.set_function_code(python_codes[0].python_code)

        # 更新执行状态
        case_execution.status = 'running'
        case_execution.save()

        # 准备测试数据
        case = case_execution.case
        interface = case.interface
        # project = interface.project

        case_data = {
            'method': interface.method,
            'url': execute_env + interface.path,
            # 'headers': interface.headers or {},
            'headers': case.headers or {},
            'body': case.body,
            'params': case.params,
            'data': case.data,
            'body_type': case.body_type
        }

        # 执行请求
        start_time = time.time()
        executor = RequestExecutor(vp)

        try:
            log.info('🚀 before 执行测试用例')
            response, actual_reqeust_data = executor.execute(case_data)
            log.info('🚀 after 执行测试用例')
            # 记录请求数据（变量替换后）
            case_execution.request_data = actual_reqeust_data

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
                # 'body': response.json() if response.text else {}
                'body': response.text
            }
            # 执行断言
            assertion_result = []
            all_passed = True
            for assertion in case.assertions:
                if not assertion:
                    continue
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

            case_execution.assertions_result = assertion_result
            case_execution.status = 'passed' if all_passed else 'failed'

        except Exception as e:
            # 处理请求级异常
            case_execution.status = 'failed'
            case_execution.response_data = {'error': str(e)}
            case_execution.duration = round(time.time() - start_time, 3)

        # 保存最终结果
        case_execution.save()

    except Exception as e:
        # 处理请求级异常
        case_execution.status = 'failed'
        case_execution.response_data = {'error': str(e)}
        case_execution.duration = 0
        log.error(f"执行用例失败: {str(e)}")
