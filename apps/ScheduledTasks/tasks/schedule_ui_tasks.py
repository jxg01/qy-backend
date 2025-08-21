# schedule_ui_tasks.py  —— 异常安全版
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy-backend.settings')
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

log = logging.getLogger('celery.task')


@shared_task
def execute_batch_ui_tests(task_id):
    """批量执行所有启用的UI测试用例"""
    log.info(f"UI测试用例 === execute_batch_ui_tests start, task_id【{task_id}】")

    # 1. 取任务 & 用例
    try:
        scheduled_task = ScheduledTask.objects.get(id=task_id)
        test_cases = UiTestCase.objects.filter(enable=True)
        if not test_cases.exists():
            log.info("没有启用的UI测试用例可执行")
            return "没有启用的UI测试用例可执行"
    except ScheduledTask.DoesNotExist:
        log.error(f"任务 ID {task_id} 不存在")
        return f"任务 ID {task_id} 不存在"

    # 2. 创建顶层任务结果
    try:
        scheduled_task_result = ScheduledTaskResult.objects.create(
            schedule=scheduled_task,
            start_time=timezone.now(),
            executor='System',
            status='running',
        )
    except Exception as e:
        log.error(f"创建调度任务结果失败: {str(e)}")
        return f"创建调度任务结果失败: {str(e)}"

    # 3. 逐条用例执行
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

            # 真正运行
            case_status, logs, screenshot, execution_log = asyncio.run(
                run_ui_case_tool(
                    case_json=case_json,
                    browser_type=settings.UI_TEST_BROWSER_TYPE
                )
            )
            execution.status = case_status
            execution.steps_log = execution_log
            execution.screenshot = screenshot
            execution.duration = round(time.time() - execution.executed_at.timestamp(), 3)
            execution.save()
            log.info(f"用例 {test_case.name} 完成，状态: {case_status}")

        except Exception as e:   # 捕获单条用例执行异常
            log.error(f"用例 {test_case.name} 执行异常: {str(e)}", exc_info=True)
            execution = UiExecution.objects.create(
                testcase=test_case,
                status='failed',
                executed_by=test_case.created_by,
                scheduled_task_result=scheduled_task_result,
                steps_log=str(e),
            )
            execution.save()

    # 4. 更新顶层结果
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
