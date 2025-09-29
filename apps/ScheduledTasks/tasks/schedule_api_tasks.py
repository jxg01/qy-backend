from celery import shared_task

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy_backend.settings')
import django
django.setup()

import logging
import time
from django.utils import timezone
from celery import shared_task
from ScheduledTasks.models import ScheduledTaskResult
# from common.handle_test.runcase import run_test_case_tool  # 导入实际的API测试运行工具

log = logging.getLogger('app')


@shared_task
def run_all_api_test(project_id, result_id=None):
    """执行项目的API测试用例"""
    log.info(f"API测试任务 === run_all_api_test start, project_id【{project_id}】, result_id【{result_id}】")
    
    # 1. 获取或创建任务结果记录
    try:
        if result_id:
            # 使用传入的result_id对应的记录
            scheduled_task_result = ScheduledTaskResult.objects.get(id=result_id)
            log.info(f"使用已有的任务结果记录: {result_id}")
        else:
            # 自动触发时创建新记录
            # 这里需要获取关联的ScheduledTask对象，假设有一个project_id到task的映射
            # 实际实现可能需要根据项目结构调整
            from ScheduledTasks.models import ScheduledTask
            scheduled_tasks = ScheduledTask.objects.filter(project_id=project_id)
            if scheduled_tasks.exists():
                scheduled_task = scheduled_tasks.first()
                scheduled_task_result = ScheduledTaskResult.objects.create(
                    schedule=scheduled_task,
                    start_time=timezone.now(),
                    executor='System',
                    trigger='auto',  # 自动触发
                    status='running',
                )
            else:
                log.warning(f"未找到项目ID为{project_id}的定时任务")
                return f"未找到项目ID为{project_id}的定时任务"
    except Exception as e:
        log.error(f"获取或创建任务结果记录失败: {str(e)}")
        return f"获取或创建任务结果记录失败: {str(e)}"
    
    try:
        # 2. 实际执行API测试用例的逻辑
        # 这里应该根据项目ID获取测试用例并执行
        # 暂时使用测试逻辑，实际实现需替换为真实的API测试运行代码
        log.info(f"开始执行项目 {project_id} 的API测试")
        
        # 模拟API测试执行
        time.sleep(3)  # 模拟执行时间
        
        # 如果有实际的API测试运行工具，可以调用它
        # results = run_test_case_tool(project_id=project_id)  # 示例调用
        
        # 3. 更新任务结果状态为完成
        scheduled_task_result.status = 'completed'
        scheduled_task_result.end_time = timezone.now()
        scheduled_task_result.duration = round(
            (scheduled_task_result.end_time - scheduled_task_result.start_time).total_seconds(), 3
        )
        scheduled_task_result.save()
        
        log.info(f"API测试任务完成，项目ID: {project_id}")
        return f"API测试任务完成，项目ID: {project_id}"
    except Exception as e:
        log.error(f"API测试执行失败: {str(e)}")
        # 更新任务结果状态为失败
        scheduled_task_result.status = 'failed'
        scheduled_task_result.end_time = timezone.now()
        scheduled_task_result.duration = round(
            (scheduled_task_result.end_time - scheduled_task_result.start_time).total_seconds(), 3
        )
        scheduled_task_result.save()
        return f"API测试执行失败: {str(e)}"
