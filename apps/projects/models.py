from django.db import models
from django.utils import timezone
from users.models import UserProfile


class Projects(models.Model):
    class Meta:
        db_table = 'qy_projects'
        verbose_name_plural = verbose_name = '项目'
        ordering = ['-created_at']

    name = models.CharField(max_length=10, verbose_name='项目名称', help_text='项目名称')
    description = models.TextField(blank=True, verbose_name='描述', help_text='描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="创建人",
        related_name='created_project',
        default=1
    )
    updated_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="更新人",
        related_name='updated_project',
        default=1
    )

    def __str__(self):
        return self.name


class GlobalVariable(models.Model):
    class Meta:
        db_table = 'qy_global_variable'
        verbose_name_plural = verbose_name = '全局变量'

    name = models.CharField(max_length=16, verbose_name='变量名称', help_text='变量名称')
    value = models.CharField(max_length=16, verbose_name='变量值', help_text='变量值')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="创建人",
        related_name='created_globalvariables'
    )
    updated_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="更新人",
        related_name='updated_globalvariables'
    )

    def __str__(self):
        return self.name


class ProjectEnvs(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, verbose_name='关联项目', help_text='关联项目', related_name='envs')
    name = models.CharField(max_length=60, verbose_name='环境名称', help_text='环境名称')
    url = models.CharField(max_length=60, verbose_name='环境地址', help_text='环境地址')
    description = models.CharField(max_length=240, verbose_name='环境地址', help_text='环境地址')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="创建人",
        related_name='created_project_envs'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    updated_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="编辑人",
        related_name='updated_project_envs'
    )

    class Meta:
        db_table = 'qy_project_envs'
        verbose_name_plural = verbose_name = '项目环境信息'


class PythonCode(models.Model):
    name = models.CharField(max_length=60, verbose_name='代码名称', help_text='代码名称')
    python_code = models.TextField(null=True, verbose_name='代码内容', help_text='代码内容')
    description = models.CharField(max_length=240, verbose_name='代码描述', help_text='代码描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="创建人",
        related_name='created_python_code'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    updated_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="编辑人",
        related_name='updated_python_code'
    )

    class Meta:
        db_table = 'qy_python_code'
        verbose_name_plural = verbose_name = 'Python代码'


class DBConfig(models.Model):
    env = models.OneToOneField(ProjectEnvs, on_delete=models.CASCADE,
                               verbose_name='关联环境', help_text='关联环境', related_name='db_config')
    name = models.CharField(max_length=60, verbose_name='数据库名称', help_text='数据库名称')
    host = models.CharField(max_length=60, verbose_name='数据库地址', help_text='数据库地址')
    port = models.IntegerField(default=3306, verbose_name='端口号', help_text='端口号')
    username = models.CharField(max_length=60, verbose_name='用户名', help_text='用户名')
    password = models.CharField(max_length=60, verbose_name='密码', help_text='密码')
    description = models.CharField(max_length=240, verbose_name='描述', help_text='描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="创建人",
        related_name='created_db_config'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    updated_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="编辑人",
        related_name='updated_db_config'
    )

    class Meta:
        db_table = 'qy_db_config'
        verbose_name_plural = verbose_name = '数据库配置'
