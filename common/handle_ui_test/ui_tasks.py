from celery import shared_task

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy-backend.settings')
import django
django.setup()

from common.handle_ui_test.ui_runner import run_ui_case_tool
import asyncio
from ui_case.models import UiExecution, UiTestCase  # 假设模型放在 ui app 中
import logging
import time

log = logging.getLogger('celery.task')


@shared_task
def run_ui_test_case(execution_id: int, browser_type: str, is_headless):
    start_time = time.time()
    execution = UiExecution.objects.get(id=execution_id)
    try:
        log.info(f'🚀 开始执行UI用例: {execution.testcase.name}, 执行人: {execution.executed_by.username}')
        testcase = execution.testcase

        case_json = {
            'pre_apis': testcase.pre_apis,
            'steps': testcase.steps,
            'post_steps': testcase.post_steps
        }
        # execution.status = 'running'
        execution.save()
        log.info('开始执行.............')
        case_status, logs, screenshot, execution_log = asyncio.run(
            run_ui_case_tool(case_json=case_json,
                             is_headless=is_headless,
                             browser_type=browser_type)
        )
        log.info('执行完成，准备收集结果.............')

        execution.duration = round(time.time() - start_time, 3)
        execution.status = case_status
        execution.steps_log = execution_log
        execution.screenshot = screenshot
        log.info('收集结果完成，准备提交数据库save.............')
        execution.save()
        log.info('🚀 数据库save成功.............')

    except Exception as e:
        log.error(f'Ui Test Case Tasks Execute Error => {str(e)}')
        execution.status = 'failed'
        log.error('执行失败，准备收集结果.............status == failed')
        execution.duration = round(time.time() - start_time, 3)
        execution.save()
        log.error(f'保存执行结果为failed，准备结束任务............. status= {execution.status} execution id ={execution.id}')
