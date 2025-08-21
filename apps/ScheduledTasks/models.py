from django.db import models
from users.models import UserProfile


class ScheduledTask(models.Model):
    TASK_TYPE_CHOICES = (
        ("api", "API 测试"),
        ("ui", "UI 测试"),
    )
    task_type = models.CharField(max_length=10, choices=TASK_TYPE_CHOICES, default="api")
    name = models.CharField(max_length=100)
    cron = models.CharField(max_length=100)  # cron 表达式
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='%(class)s_created'
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='%(class)s_updated'
    )


class ScheduledTaskResult(models.Model):
    schedule = models.ForeignKey(
        ScheduledTask,
        on_delete=models.CASCADE,
        related_name='results'
    )
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.FloatField(default=0)  # 持续时间，单位秒
    executor = models.CharField(max_length=100)
    trigger = models.CharField(max_length=50, default="auto", help_text="manual or auto")  # 手动触发或定时触发
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed")
        ],
        default="pending"
    )

    def __str__(self):
        return f"Result for {self.schedule.name} at {self.start_time}"
