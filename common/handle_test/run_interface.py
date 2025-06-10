import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy-backend.settings')
import django
django.setup()

from common.handle_test.variable_pool import VariablePool
from common.handle_test.request_executor import RequestExecutor
import logging
from projects.models import GlobalVariable

log = logging.getLogger('django')


def execute_interface(payload):
    """异步执行单个测试用例任务
    payload = {
        'method': localDetail.method,
        'url': command + localDetail.path,
        'headers': localDetail.headers,
        'params': localDetail.params,
        'body_type': localDetail.bodyType,
        'data': localDetail.data,
        'body': localDetail.body
    }
    """
    log.info('🚀 开始执行测试用例')
    request_result = {}
    try:
        # 更新全局变量
        # 初始化变量池
        vp = VariablePool()
        global_vars = GlobalVariable.objects.values_list('name', 'value')
        vp.update_global({name: value for name, value in global_vars})

        executor = RequestExecutor(vp)

        response, actual_reqeust_data = executor.execute(payload)

        # 记录请求数据（变量替换后）
        request_result['request_data'] = actual_reqeust_data

        # 记录响应数据
        # request_result['response_data'] = {"a": 2}
        request_result['response_data'] = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'body': response.text
        }
    except Exception as e:
        log.error(f"执行测试用例失败: {e}")
        request_result['response_data'] = {'error': str(e)}
    finally:
        log.info('🚀 测试用例执行完成')
        return request_result
