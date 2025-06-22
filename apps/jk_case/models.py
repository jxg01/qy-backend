from django.db import models
from django.utils import timezone
# from django.contrib.auth.models import User
from users.models import UserProfile
from projects.models import Projects


# 抽象基类减少重复
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='%(class)s_created'
    )
    updated_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='%(class)s_updated'
    )

    class Meta:
        abstract = True


class Module(TimeStampedModel):
    # 模型
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='modules', verbose_name="所属项目")
    parent_module = models.ForeignKey('self', on_delete=models.CASCADE, null=True,
                                      blank=True, related_name='submodules', verbose_name="父模块")
    name = models.CharField(max_length=100, verbose_name="模块名称")
    # order = models.PositiveIntegerField(default=0, verbose_name="排序")

    class Meta:
        db_table = 'qy_module'
        ordering = ['name']
        unique_together = [('project', 'name')]  # 同一项目内模块名称唯一

    def __str__(self):
        return f"{self.project.name} - {self.name}"


# class UserTrackedModel(models.Model):
#     created_by = models.ForeignKey(
#         UserProfile,
#         on_delete=models.CASCADE,
#         related_name='%(class)s_created'
#     )
#     updated_by = models.ForeignKey(
#         UserProfile,
#         on_delete=models.CASCADE,
#         related_name='%(class)s_updated'
#     )
#
#     class Meta:
#         abstract = True


class TestSuite(TimeStampedModel):
    class Meta:
        db_table = 'qy_suite'
        verbose_name_plural = verbose_name = '测试套件'

    project = models.ForeignKey(Projects, on_delete=models.CASCADE, verbose_name='项目名称', help_text='项目名称')
    name = models.CharField(max_length=30, unique=True, verbose_name='套件名称', help_text='套件名称')
    description = models.CharField(max_length=100, null=True, verbose_name='套件描述', help_text='套件描述')
    # 指定中间模型 through
    cases = models.ManyToManyField('TestCase', through='SuiteCaseRelation', verbose_name='用例1', help_text='用例')

    def __str__(self):
        return self.name


class InterFace(TimeStampedModel):
    METHOD_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE'),
        ('PATCH', 'PATCH'),
    ]

    # project = models.ForeignKey(  # 字段重命名
    #     Projects,
    #     on_delete=models.CASCADE,
    #     verbose_name='所属项目'
    # )

    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='interface',
        verbose_name="所属模块",
        null=True,
    )
    name = models.CharField(
        max_length=30,
        verbose_name='接口名称',
    )
    path = models.CharField(max_length=500, verbose_name='接口路径')  # 增加长度
    method = models.CharField(
        max_length=10,
        choices=METHOD_CHOICES,  # 限制选项
        verbose_name='请求方式'
    )

    class Meta:
        db_table = 'qy_interface'
        verbose_name = verbose_name_plural = '接口用例'

    def __str__(self):
        return self.name


class TestCase(TimeStampedModel):
    class Meta:
        db_table = 'qy_test_case'
        verbose_name = verbose_name_plural = '测试用例'

    interface = models.ForeignKey(InterFace, on_delete=models.CASCADE, verbose_name='接口')
    name = models.CharField(max_length=30, verbose_name='用例名称')
    description = models.CharField(max_length=100, null=True, verbose_name='用例描述')
    headers = models.JSONField(  # 改为JSON字段
        default=dict,
        verbose_name='请求头'
    )
    params = models.JSONField(  # 改为JSON字段
        default=dict,
        verbose_name='查询参数'
    )

    body_type = models.CharField(max_length=10, default='form',
                                 verbose_name='请求体类型: form | raw',
                                 help_text='请求体类型: form | raw')

    data = models.JSONField(  # 改为JSON字段
        default=dict,
        verbose_name='请求参数'
    )

    body = models.CharField(
        max_length=1024,
        null=True,
        verbose_name='请求体：json字符串',
        help_text='请求体：json字符串'
    )
    # # [{'type': 'status_code', 'expected': 200}, {'type': 'jsonpath', 'path': '$.status', 'expected': 200}]
    assertions = models.JSONField(  # 结构化存储
        default=list,
        verbose_name='断言规则'
    )
    # extract_rules = [{"name": "user_id", "path": "$.data.user.id"},{"name": "token", "path": "$.data.token"}]
    variable_extract = models.JSONField(  # 结构化存储
        default=list,
        verbose_name='变量提取规则'
    )
    enabled = models.BooleanField(
        default=True,
        verbose_name='是否启用'
    )


class SuiteCaseRelation(models.Model):
    class Meta:
        db_table = 'qy_suite_case_relation'
        ordering = ['order']
        # 防止重复添加用例
        unique_together = [('suite', 'case')]

    suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE)
    case = models.ForeignKey(TestCase, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0, verbose_name='执行顺序')


# 执行记录拆分为两个模型
class TestExecution(models.Model):
    """套件执行记录"""
    class Meta:
        db_table = 'qy_test_execution'
    STATUS_CHOICES = [
        ('pending', '未开始'),
        ('running', '执行中'),
        ('passed', '成功'),
        ('failed', '失败')
    ]

    suite = models.ForeignKey(
        TestSuite,
        on_delete=models.CASCADE,
        verbose_name='测试套件'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True)
    duration = models.FloatField(null=True)
    executed_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True
    )


class CaseExecution(models.Model):
    """用例执行详情"""
    class Meta:
        db_table = 'qy_case_execution'
    execution = models.ForeignKey(
        TestExecution,
        on_delete=models.SET_NULL,
        related_name='cases',
        null=True,
        blank=True,
    )
    case = models.ForeignKey(
        TestCase,
        on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=20,
        choices=TestExecution.STATUS_CHOICES
    )
    request_data = models.JSONField(default=dict)  # 结构化存储
    response_data = models.JSONField(default=dict)
    assertions_result = models.JSONField(default=list)
    extracted_vars = models.JSONField(default=list)
    duration = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True
    )
