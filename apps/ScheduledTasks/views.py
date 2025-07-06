# views.py
from rest_framework import viewsets, status
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from .models import ScheduledTask
from .serializers import ScheduledTaskSerializer


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
        task = serializer.save(updated_by=self.request.user)
        self._create_or_update_periodic_task(task)

    def perform_destroy(self, instance):
        PeriodicTask.objects.filter(name=f"scheduled_task_{instance.id}").delete()
        instance.delete()

    def _create_or_update_periodic_task(self, task):
        cron_parts = task.cron.strip().split()
        if len(cron_parts) != 5:
            raise ValueError("Invalid cron expression")

        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=cron_parts[0],
            hour=cron_parts[1],
            day_of_month=cron_parts[2],
            month_of_year=cron_parts[3],
            day_of_week=cron_parts[4],
        )

        if task.task_type == "api":
            task_name = "testtasks.tasks.run_suite_task"
        else:
            task_name = "ui_run_tasks.run_ui_suite_task"

        PeriodicTask.objects.update_or_create(
            name=f"scheduled_task_{task.id}",
            defaults={
                "crontab": schedule,
                # "task": "testtasks.tasks.run_suite_task",
                "task": task_name,
                "enabled": task.enabled,
                # "args": json.dumps([task.suite_id]),
            }
        )
