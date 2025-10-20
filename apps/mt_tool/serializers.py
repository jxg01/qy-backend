from rest_framework import serializers
from mt_tool.models import MTToolConfig


class MTToolConfigSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    created_by = serializers.CharField(
        source='created_by.username',
        read_only=True,
        help_text="创建人"
    )
    updated_by = serializers.CharField(
        source='updated_by.username',
        read_only=True,
        help_text="更新人"
    )

    class Meta:
        model = MTToolConfig
        fields = '__all__'
        ordering = ['-id']
