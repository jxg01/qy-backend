from rest_framework import serializers
from .models import TaskRecord


class TaskRecordSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = TaskRecord
        fields = ['id', 'user', 'task_id', 'parameters', 'status',
                  'created_at', 'updated_at', 'result']
