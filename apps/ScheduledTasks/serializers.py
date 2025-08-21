from ScheduledTasks.models import ScheduledTask, ScheduledTaskResult
from rest_framework import serializers
from common.exceptions import BusinessException
from common.error_codes import ErrorCode
import re


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
    schedule = serializers.StringRelatedField(read_only=True)
    start_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    end_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")

    # 从UiExecution模型动态获取的字段
    total = serializers.SerializerMethodField()
    passed = serializers.SerializerMethodField()
    failed = serializers.SerializerMethodField()
    error = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    test_cases_result = serializers.SerializerMethodField()

    class Meta:
        model = ScheduledTaskResult
        fields = ['id', 'schedule', 'start_time', 'end_time', 'duration', 'executor', 'trigger', 'created_at', 'total', 'passed', 'failed', 'error', 'success_rate', 'test_cases_result']

    def get_total(self, obj):
        # 通过外键关系获取该调度任务结果相关的所有UI执行记录
        from ui_case.models import UiExecution
        
        executions = UiExecution.objects.filter(scheduled_task_result=obj)
        return executions.count()

    def get_passed(self, obj):
        from ui_case.models import UiExecution
        
        # 通过外键关系获取该调度任务结果相关的通过的UI执行记录
        passed_executions = UiExecution.objects.filter(
            scheduled_task_result=obj,
            status='passed'
        )
        return passed_executions.count()

    def get_failed(self, obj):
        from ui_case.models import UiExecution
        
        # 通过外键关系获取该调度任务结果相关的失败的UI执行记录
        failed_executions = UiExecution.objects.filter(
            scheduled_task_result=obj,
            status='failed'
        )
        return failed_executions.count()

    def get_error(self, obj):
        from ui_case.models import UiExecution
        
        # 通过外键关系获取该调度任务结果相关的错误的UI执行记录
        # 假设没有直接的error状态，暂时将failed视为error
        error_executions = UiExecution.objects.filter(
            scheduled_task_result=obj,
            status='failed'
        )
        return error_executions.count()

    def get_success_rate(self, obj):
        # 计算成功率
        total = self.get_total(obj)
        if total == 0:
            return 0
        return round((self.get_passed(obj) / total) * 100, 2)

    def get_test_cases_result(self, obj):
        from ui_case.models import UiExecution
        
        # 通过外键关系获取该调度任务结果相关的所有UI执行记录
        executions = UiExecution.objects.filter(scheduled_task_result=obj)
        
        # 构建测试用例结果列表
        results = []
        for execution in executions:
            result = {
                'case_id': execution.testcase.id,
                'case_name': execution.testcase.name,
                'status': execution.status,
                'duration': execution.duration,
                'error_message': execution.steps_log.get('error', '') if isinstance(execution.steps_log, dict) else '',
                'executed_at': execution.executed_at.strftime('%Y-%m-%d %H:%M:%S')
            }
            results.append(result)
        
        return results
