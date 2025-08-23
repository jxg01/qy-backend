from ScheduledTasks.models import ScheduledTask, ScheduledTaskResult
from rest_framework import serializers
from common.exceptions import BusinessException
from common.error_codes import ErrorCode
import re
from ui_case.models import UiExecution
from django.utils.timezone import localtime


class ScheduledTaskSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    updated_by = serializers.StringRelatedField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")
    updated_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = ScheduledTask
        fields = '__all__'

    def validate_cron(self, value):
        """
        验证 cron 表达式的格式
        """
        parts = value.strip().split()
        if len(parts) != 5:
            raise BusinessException(ErrorCode.CRON_ERROR)

        # 使用正则表达式校验每个部分
        cron_regex = r'^(\*|([0-9]|[1-5][0-9])|([0-9]-[0-9])|(\*/[0-9]+))$'
        for part in parts:
            if not re.match(cron_regex, part):
                raise BusinessException(ErrorCode.CRON_ERROR)
        return value


class ScheduledTaskResultSerializer(serializers.ModelSerializer):
    # schedule = serializers.StringRelatedField(read_only=True)
    schedule_name = serializers.CharField(source='schedule.name', read_only=True)  # 取外键表的 name 字段
    start_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    end_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")

    # 从UiExecution模型动态获取的字段
    total = serializers.SerializerMethodField()
    passed = serializers.SerializerMethodField()
    failed = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    test_cases_result = serializers.SerializerMethodField()

    class Meta:
        model = ScheduledTaskResult
        fields = ['id', 'schedule', 'schedule_name', 'start_time', 'end_time', 'duration', 'executor',
                  'trigger', 'created_at', 'total', 'passed', 'failed', 'success_rate', 'status', 'test_cases_result']

    def get_total(self, obj):
        # 通过外键关系获取该调度任务结果相关的所有UI执行记录
        executions = UiExecution.objects.filter(scheduled_task_result=obj)
        return executions.count()

    def get_passed(self, obj):
        # 通过外键关系获取该调度任务结果相关的通过的UI执行记录
        passed_executions = UiExecution.objects.filter(
            scheduled_task_result=obj,
            status='passed'
        )
        return passed_executions.count()

    def get_failed(self, obj):
        # 通过外键关系获取该调度任务结果相关的失败的UI执行记录
        failed_executions = UiExecution.objects.filter(
            scheduled_task_result=obj,
            status='failed'
        )
        return failed_executions.count()

    # def get_error(self, obj):
    #     # 通过外键关系获取该调度任务结果相关的错误的UI执行记录
    #     # 假设没有直接的error状态，暂时将failed视为error
    #     error_executions = UiExecution.objects.filter(
    #         scheduled_task_result=obj,
    #         status='failed'
    #     )
    #     return error_executions.count()

    def get_success_rate(self, obj):
        # 计算成功率
        total = self.get_total(obj)
        if total == 0:
            return 0
        return round((self.get_passed(obj) / total) * 100, 2)

    def get_test_cases_result(self, obj):

        # 通过外键关系获取该调度任务结果相关的所有UI执行记录
        executions = UiExecution.objects.filter(scheduled_task_result=obj).values(
            'id', 'testcase__name', 'status', 'duration', 'executed_at', 'executed_by__username',
            'steps_log', 'screenshot', 'browser_info'
        ).order_by('-executed_at')
        # Convert executed_at to China timezone
        for execution in executions:
            execution['executed_at'] = localtime(execution['executed_at']).strftime('%Y-%m-%d %H:%M:%S')
        return list(executions)
