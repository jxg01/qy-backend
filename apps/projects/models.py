from django.db import models
from django.utils import timezone
from users.models import UserProfile


class Projects(models.Model):
    class Meta:
        db_table = 'qy_projects'
        verbose_name_plural = verbose_name = '项目'
        ordering = ['-created_at']

    name = models.CharField(max_length=10, verbose_name='项目名称', help_text='项目名称')
    base_url = models.CharField(max_length=30, verbose_name='项目地址', help_text='项目地址')
    description = models.TextField(blank=True, verbose_name='描述', help_text='描述')
    # modify_time = models.DateTimeField(auto_now=True, verbose_name='修改时间', help_text='修改时间')
    # create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间', help_text='创建时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    creator = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="created_projects",
        verbose_name="创建人"
    )
    # creator = models.ForeignKey('users.UserProfile', on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class GlobalVariable(models.Model):
    class Meta:
        db_table = 'qy_global_variable'
        verbose_name_plural = verbose_name = '全局变量'

    name = models.CharField(max_length=16, verbose_name='变量名称', help_text='变量名称')
    value = models.CharField(max_length=16, verbose_name='变量值', help_text='变量值')
    # project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='global_variables', verbose_name="项目")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="created_global_variables",
        verbose_name="创建人"
    )
    updated_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="updated_global_variables",
        verbose_name="更新人"
    )

    def __str__(self):
        return self.name
