from django.db import models
from django.contrib.auth.models import User
from projects.models import Projects


class UiElement(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    locator_type = models.CharField(max_length=20, choices=[("xpath", "XPath"), ("css", "CSS"), ("id", "ID")])
    locator_value = models.CharField(max_length=256)
    description = models.TextField(blank=True)


class UiTestCase(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    steps = models.JSONField(default=list)  # 步骤为结构化JSON
    browser = models.CharField(max_length=20, default='chrome')
    enable = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class UiExecution(models.Model):
    testcase = models.ForeignKey(UiTestCase, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("success", "Success"), ("fail", "Fail")])
    logs = models.TextField()
    screenshots = models.JSONField(default=list)
    duration = models.FloatField()
    executed_at = models.DateTimeField(auto_now_add=True)

