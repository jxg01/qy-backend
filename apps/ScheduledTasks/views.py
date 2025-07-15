# views.py
from rest_framework import viewsets
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from .models import ScheduledTask
from .serializers import ScheduledTaskSerializer
import logging

log = logging.getLogger('django')


class ScheduledTaskViewSet(viewsets.ModelViewSet):
    queryset = ScheduledTask.objects.all()
    serializer_class = ScheduledTaskSerializer

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
            task_name = "ScheduledTasks.tasks.schedule_ui_tasks.run_all_ui_test"
            # cases = ui_case.objects.filter(module=task.module)
        PeriodicTask.objects.update_or_create(
            name=f"scheduled_task_{task.id}",
            defaults={
                "crontab": schedule,
                "task": task_name,
                "enabled": task.enabled,
                # "args": json.dumps([cases]),
            }
        )
