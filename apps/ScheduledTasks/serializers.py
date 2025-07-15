from ScheduledTasks.models import ScheduledTask
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
