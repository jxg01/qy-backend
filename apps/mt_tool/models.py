from django.db import models
from users.models import UserProfile


class TaskRecord(models.Model):
    STATUS_CHOICES = (
        ('pending', '等待中'),
        ('running', '运行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
        ('cancelled', '已取消'),
    )

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    task_id = models.CharField(max_length=255, unique=True)
    parameters = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    result = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.task_id} - {self.status}"

    class Meta:
        db_table = 'qy_task_record'
