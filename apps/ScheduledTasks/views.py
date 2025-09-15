# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from .models import ScheduledTask, ScheduledTaskResult
from .serializers import ScheduledTaskSerializer, ScheduledTaskResultSerializer
import logging
import json
from django.utils import timezone

log = logging.getLogger('django')


class ScheduledTaskViewSet(viewsets.ModelViewSet):
    queryset = ScheduledTask.objects.all().order_by('-id')
    serializer_class = ScheduledTaskSerializer

    def get_queryset(self):
        project_id = self.request.query_params.get('project_id')
        if project_id:
            return self.queryset.filter(project_id=project_id)
        return self.queryset

    def perform_create(self, serializer):
        """
        POST /api/schedule/
        {
          "name": "每天早上跑 smoke 套件",
          "suite_id": 12,
          "cron": "0 9 * * *",
          "enabled": true
        }
        """
        task = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        self._create_or_update_periodic_task(task)

    def perform_update(self, serializer):
        old_instance = self.get_object()
        task = serializer.save(updated_by=self.request.user)
        log.info(
            f"User ({self.request.user}) updated scheduled task. "
            f"Changes: task name (old: {old_instance.name}, new: {task.name}), "
            f"Changes: cron (old: {old_instance.cron}, new: {task.cron}), "
            f"enabled (old: {old_instance.enabled}, new: {task.enabled}), "
            f"task_type (old: {old_instance.task_type}, new: {task.task_type})."
        )

        self._create_or_update_periodic_task(task)

    def perform_destroy(self, instance):
        PeriodicTask.objects.filter(name=f"scheduled_task_{instance.id}").delete()
        instance.delete()

    def _create_or_update_periodic_task(self, task):
        cron_parts = task.cron.strip().split()
        # 如果是跑冒烟，需要给用例增加一个tag：smoke
        # if task.type == smoke:  testcase.objects.filter(smoke=true)

        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=cron_parts[0],
            hour=cron_parts[1],
            day_of_month=cron_parts[2],
            month_of_year=cron_parts[3],
            day_of_week=cron_parts[4],
        )

        if task.task_type == "api":
            task_name = "ScheduledTasks.tasks.module_run_test.run_test_api_case"
            # 获取module下的用例，需要修改定时任务可以选择module
            # cases = interface.objects.filter(module=task.module)
        else:
            task_name = "ScheduledTasks.tasks.schedule_ui_tasks.execute_batch_ui_tests"
            # cases = ui_case.objects.filter(module=task.module)
        PeriodicTask.objects.update_or_create(
            name=f"scheduled_task_{task.id}",
            defaults={
                "crontab": schedule,
                "task": task_name,
                "enabled": task.enabled,
                "args": json.dumps([task.id]),
            }
        )
        
    @action(detail=True, methods=['post'], url_path='run-manually')
    def run_manually(self, request, pk=None):
        """
        手动运行定时任务
        URL: /api/scheduled-tasks/{id}/run-manually/
        """
        try:
            # 获取任务对象
            scheduled_task = self.get_object()
            
            # 创建任务执行结果记录
            scheduled_task_result = ScheduledTaskResult.objects.create(
                schedule=scheduled_task,
                start_time=timezone.now(),
                executor=request.user.username,
                trigger='manual',  # 标记为手动触发
                status='running',
            )
            
            # 根据任务类型执行相应的任务
            if scheduled_task.task_type == "ui":
                # UI测试任务
                from ScheduledTasks.tasks.schedule_ui_tasks import execute_batch_ui_tests
                # 传递result_id，避免重复创建记录
                execute_batch_ui_tests.delay(scheduled_task.id, scheduled_task_result.id)
                task_name = "UI测试任务"
            else:
                # API测试任务
                task_name = "API测试任务"
                # 使用run_all_api_test任务，确保与现有实现兼容
                # from ScheduledTasks.tasks.schedule_api_tasks import run_all_api_test
                # 传递项目ID和结果ID
                # run_all_api_test.delay(scheduled_task.project.id, scheduled_task_result.id)
            
            log.info(f"用户 {request.user} 手动触发了定时任务: {scheduled_task.name} (ID: {scheduled_task.id})")
            
            return Response({
                "code": 0,
                "message": f"{task_name}已手动触发，正在执行中",
                "data": {
                    "task_id": scheduled_task.id,
                    "task_name": scheduled_task.name,
                    "result_id": scheduled_task_result.id
                }
            })
        except ScheduledTask.DoesNotExist:
            log.error(f"定时任务ID {pk} 不存在")
            return Response({
                "code": 404,
                "message": f"定时任务ID {pk} 不存在"
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.error(f"手动触发定时任务失败: {str(e)}")
            return Response({
                "code": 500,
                "message": f"手动触发定时任务失败: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ScheduledTaskResultViewSet(viewsets.ModelViewSet):
    queryset = ScheduledTaskResult.objects.all().order_by('-id')
    serializer_class = ScheduledTaskResultSerializer

    def get_queryset(self):
        schedule_id = self.request.query_params.get('schedule_id')
        if schedule_id:
            return self.queryset.filter(schedule_id=schedule_id)
        return self.queryset
