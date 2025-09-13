from celery import shared_task

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy-backend.settings')
import django

django.setup()

from common.handle_ui_test.ui_runner import run_ui_case_tool
import asyncio
from ui_case.models import UiExecution, UiTestCase
import logging
import time
import tempfile

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

        execution.save()
        log.info('开始执行.............')

        # 确定是否使用存储状态
        storage_state_path = None

        # 检查是否有关联的登录用例
        if testcase.login_case:
            log.info(f"用例关联了登录用例: {testcase.login_case.name}")

            # 创建临时文件用于存储登录状态
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            storage_state_path = temp_file.name
            temp_file.close()

            # 执行登录用例
            login_case_json = {
                'pre_apis': testcase.login_case.pre_apis,
                'steps': testcase.login_case.steps,
                'post_steps': testcase.login_case.post_steps
            }

            login_status, login_logs, login_screenshot, login_execution_log = asyncio.run(
                run_ui_case_tool(
                    case_json=login_case_json,
                    is_headless=is_headless,
                    browser_type=browser_type,
                    storage_state_path=storage_state_path,
                    save_storage_state=True
                )
            )
            log.info(f"登录用例执行状态: {login_status}")
            log.info(f"登录用例执行日志: {login_execution_log}")

            if login_status != 'passed':
                log.error(f"登录用例执行失败，状态: {login_status}")
                execution.status = 'failed'
                execution.steps_log = f"依赖的登录用例执行失败: {login_status}"
                execution.duration = round(time.time() - start_time, 3)
                execution.save()
                return

        # 执行当前用例
        case_status, logs, screenshot, execution_log = asyncio.run(
            run_ui_case_tool(
                case_json=case_json,
                is_headless=is_headless,
                browser_type=browser_type,
                storage_state_path=storage_state_path
            )
        )
        log.info('执行完成，准备收集结果.............')

        execution.duration = round(time.time() - start_time, 3)
        execution.status = case_status
        execution.steps_log = execution_log
        execution.screenshot = screenshot
        log.info('收集结果完成，准备提交数据库save.............')
        execution.save()
        log.info('🚀 数据库save成功.............')

        # 清理临时文件
        if storage_state_path and os.path.exists(storage_state_path):
            try:
                os.unlink(storage_state_path)
                log.info(f"已清理临时文件: {storage_state_path}")
            except Exception as e:
                log.error(f"清理临时文件失败: {str(e)}")

    except Exception as e:
        log.error(f'Ui Test Case Tasks Execute Error => {str(e)}')
        execution.status = 'failed'
        log.error('执行失败，准备收集结果.............status == failed')
        execution.duration = round(time.time() - start_time, 3)
        execution.save()
        log.error(
            f'保存执行结果为failed，准备结束任务............. status= {execution.status} execution id ={execution.id}')

        # 清理临时文件（如果存在）
        if 'storage_state_path' in locals() and storage_state_path and os.path.exists(storage_state_path):
            try:
                os.unlink(storage_state_path)
                log.info(f"已清理临时文件: {storage_state_path}")
            except Exception as e:
                log.error(f"清理临时文件失败: {str(e)}")
