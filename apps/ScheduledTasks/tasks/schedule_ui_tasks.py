import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy_backend.settings')
import django
django.setup()

from common.handle_ui_test.ui_runner import run_ui_case_tool
import asyncio
import logging
import time
from celery import shared_task
from django.utils import timezone
from ui_case.models import UiTestCase, UiExecution
from ScheduledTasks.models import ScheduledTaskResult, ScheduledTask
from django.conf import settings
from celery.utils.log import get_task_logger
import tempfile
import json

log = get_task_logger('worker')


@shared_task
def execute_batch_ui_tests(task_id, result_id=None):
    """批量执行所有启用的UI测试用例"""
    log.info(f"UI测试用例 === execute_batch_ui_tests start, task_id【{task_id}】")

    # 1. 取任务 & 用例
    try:
        scheduled_task = ScheduledTask.objects.get(id=task_id)
        test_cases = UiTestCase.objects.filter(enable=True, module__project=scheduled_task.project)
        if not test_cases.exists():
            log.info("没有启用的UI测试用例可执行")
            # 如果有result_id，更新状态为completed
            if result_id:
                try:
                    result = ScheduledTaskResult.objects.get(id=result_id)
                    result.status = 'completed'
                    result.end_time = timezone.now()
                    result.duration = round((timezone.now() - result.start_time).total_seconds(), 3)
                    result.save()
                except Exception as e:
                    log.error(f"更新任务结果状态失败: {str(e)}")
            return "没有启用的UI测试用例可执行"
    except ScheduledTask.DoesNotExist:
        log.error(f"任务 ID {task_id} 不存在")
        # 如果有result_id，更新状态为failed
        if result_id:
            try:
                result = ScheduledTaskResult.objects.get(id=result_id)
                result.status = 'failed'
                result.end_time = timezone.now()
                result.duration = round((timezone.now() - result.start_time).total_seconds(), 3)
                result.save()
            except Exception as e:
                log.error(f"更新任务结果状态失败: {str(e)}")
        return f"任务 ID {task_id} 不存在"

    # 2. 获取或创建顶层任务结果
    try:
        if result_id:
            # 使用传入的result_id对应的记录
            scheduled_task_result = ScheduledTaskResult.objects.get(id=result_id)
            log.info(f"使用已有的任务结果记录: {result_id}")
        else:
            # 定时任务自动触发时创建新记录
            scheduled_task_result = ScheduledTaskResult.objects.create(
                schedule=scheduled_task,
                start_time=timezone.now(),
                executor='System',
                trigger='auto',  # 自动触发
                status='running',
            )
    except Exception as e:
        log.error(f"获取或创建调度任务结果失败: {str(e)}")
        return f"获取或创建调度任务结果失败: {str(e)}"

    # 3. 创建临时目录用于存储上下文文件
    temp_dir = tempfile.mkdtemp(prefix=f"ui_test_storage_{task_id}_")
    log.info(f"创建临时目录: {temp_dir}")

    # 4. 存储登录用例ID到文件路径的映射
    login_case_storage_map = {}

    # 5. 逐条用例执行
    for test_case in test_cases:
        log.info(f"开始执行测试用例: {test_case.name}")
        try:
            execution = UiExecution.objects.create(
                testcase=test_case,
                status='running',
                executed_by=test_case.created_by,
                scheduled_task_result=scheduled_task_result,
                browser_info=settings.UI_TEST_BROWSER_TYPE if settings.UI_TEST_BROWSER_TYPE else 'chromium',
            )

            case_json = {
                'pre_apis': test_case.pre_apis,
                'steps': test_case.steps,
                'post_steps': test_case.post_steps
            }

            # 确定是否使用存储状态
            storage_state_path = None
            if test_case.login_case:
                login_case_id = test_case.login_case.id

                # 检查是否已有该登录用例的存储状态
                if login_case_id not in login_case_storage_map:
                    # 执行登录用例并保存存储状态
                    log.info(f"执行登录用例获取存储状态: {test_case.login_case.name}")

                    login_case_json = {
                        'pre_apis': test_case.login_case.pre_apis,
                        'steps': test_case.login_case.steps,
                        'post_steps': test_case.login_case.post_steps
                    }

                    # 创建临时文件用于存储登录状态
                    login_storage_file = tempfile.NamedTemporaryFile(
                        mode='w', suffix='.json', dir=temp_dir, delete=False
                    )
                    login_storage_path = login_storage_file.name
                    login_storage_file.close()

                    # 执行登录用例并保存存储状态
                    case_status, logs, screenshot, execution_log = asyncio.run(
                        run_ui_case_tool(
                            case_json=login_case_json,
                            browser_type=settings.UI_TEST_BROWSER_TYPE,
                            storage_state_path=login_storage_path,
                            save_storage_state=True
                        )
                    )

                    if case_status == 'passed':
                        login_case_storage_map[login_case_id] = login_storage_path
                        log.info(f"登录用例执行成功，存储状态已保存到: {login_storage_path}")
                    else:
                        log.error(f"登录用例执行失败，状态: {case_status}")
                        # 登录用例执行失败，当前用例也标记为失败
                        execution.status = 'failed'
                        execution.steps_log = f"依赖的登录用例执行失败: {case_status}"
                        execution.duration = round(time.time() - execution.executed_at.timestamp(), 3)
                        execution.save()
                        continue

                # 使用登录用例的存储状态
                storage_state_path = login_case_storage_map[login_case_id]
                log.info(f"使用登录用例的存储状态: {storage_state_path}")

            # 真正运行
            case_status, logs, screenshot, execution_log = asyncio.run(
                run_ui_case_tool(
                    case_json=case_json,
                    browser_type=settings.UI_TEST_BROWSER_TYPE,
                    storage_state_path=storage_state_path
                )
            )
            execution.status = case_status
            execution.steps_log = execution_log
            execution.screenshot = screenshot
            execution.duration = round(time.time() - execution.executed_at.timestamp(), 3)
            execution.save()
            log.info(f"用例 {test_case.name} 完成，状态: {case_status}")

        except Exception as e:  # 捕获单条用例执行异常
            log.error(f"用例 {test_case.name} 执行异常: {str(e)}", exc_info=True)
            execution = UiExecution.objects.create(
                testcase=test_case,
                status='failed',
                executed_by=test_case.created_by,
                scheduled_task_result=scheduled_task_result,
                steps_log=str(e),
            )
            execution.save()

    # 6. 清理临时目录
    try:
        import shutil
        shutil.rmtree(temp_dir)
        log.info(f"已清理临时目录: {temp_dir}")
    except Exception as e:
        log.error(f"清理临时目录失败: {str(e)}")

    # 7. 更新顶层结果
    try:
        scheduled_task_result.status = 'completed'
        scheduled_task_result.end_time = timezone.now()
        scheduled_task_result.duration = round(
            (scheduled_task_result.end_time - scheduled_task_result.start_time).total_seconds(), 3
        )
        scheduled_task_result.save()
    except Exception as e:
        log.error(f"更新任务结果失败: {str(e)}")
        scheduled_task_result.status = 'error'
        scheduled_task_result.save()

    log.info("UI测试用例执行完成...execute_batch_ui_tasks END")
