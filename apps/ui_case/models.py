from django.db import models
from projects.models import Projects
from users.models import UserProfile


class UiElement(models.Model):

    project = models.ForeignKey(Projects, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    locator_type = models.CharField(max_length=20, choices=[
        ("xpath", "XPath"),
        ("css", "CSS"),
        ("id", "ID"),
        ("name", "NAME"),
        ("class", "CLASS"),
        ("text", "TEXT")
    ])
    locator_value = models.CharField(max_length=256)
    description = models.TextField(blank=True)
    page = models.CharField(max_length=256)  # 所属页面路径
    created_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='created_elements')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='updated_elements', null=True, blank=True)

    class Meta:
        db_table = 'qy_ui_element'
        verbose_name_plural = verbose_name = 'UI元素'
        ordering = ['-created_at']


class UiTestModule(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    created_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='created_modules')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='updated_modules', null=True, blank=True)

    class Meta:
        db_table = 'qy_ui_test_module'
        verbose_name_plural = verbose_name = 'UI测试模块'
        ordering = ['-created_at']


class UiTestCase(models.Model):
    # project = models.ForeignKey(Projects, on_delete=models.CASCADE)
    module = models.ForeignKey(UiTestModule, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    pre_apis = models.JSONField(default=list)  # 前置API步骤为结构化JSON
    steps = models.JSONField(default=list)  # 步骤为结构化JSON
    post_steps = models.JSONField(default=list)  # 后置步骤为结构化JSON
    enable = models.BooleanField(default=True)
    created_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='created_cases')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='updated_cases', null=True, blank=True)

    class Meta:
        db_table = 'qy_ui_test_case'
        verbose_name_plural = verbose_name = 'UI测试用例'
        ordering = ['-created_at']


class UiExecution(models.Model):
    testcase = models.ForeignKey(UiTestCase, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=[("pending", "Pending"), ("running", "Running"),
                                ("passed", "Passed"), ("failed", "Failed")]
    )
    steps_log = models.JSONField(default={})
    screenshot = models.FileField(upload_to='screenshots/', null=True, blank=True)
    duration = models.FloatField()
    browser_info = models.CharField(max_length=128, blank=True, null=True)

    executed_at = models.DateTimeField(auto_now_add=True)
    executed_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE)


    class Meta:
        db_table = 'qy_ui_execution'
        verbose_name_plural = verbose_name = 'UI测试执行'
        ordering = ['-executed_at']


class UiTestFile(models.Model):
    name = models.CharField(max_length=128)
    file = models.FileField(upload_to='ui_test_files/')
    description = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='uploaded_files')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'qy_ui_test_file'
        verbose_name_plural = verbose_name = 'UI测试文件'
        ordering = ['-uploaded_at']
