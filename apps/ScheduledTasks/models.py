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
