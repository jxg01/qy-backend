from rest_framework import serializers
from projects.models import Projects, GlobalVariable
from common.error_codes import ErrorCode
from common.exceptions import BusinessException
import django_filters


class ProjectsFilter(django_filters.FilterSet):
    """ 定义字段，搜索方式：模糊搜索 """
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = Projects
        fields = ['name']


class GlobalVariableFilter(django_filters.FilterSet):
    """ 定义字段，搜索方式：模糊搜索 """
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = GlobalVariable
        fields = ['name']


class ProjectsSerialize(serializers.ModelSerializer):
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    creator = serializers.CharField(
        source='creator.username',
        read_only=True,
        help_text="项目创建人"
    )

    class Meta:
        model = Projects
        fields = ('id', 'name', 'base_url', 'description', 'updated_at', 'created_at', 'creator')
        # 增强字段验证规则
        extra_kwargs = {
            'name': {
                'min_length': 2,
                'max_length': 10,
                'error_messages': {
                    'min_length': '项目名称至少2个字符',
                    'max_length': '项目名称不能超过10个字符',
                    'blank': '项目名称不能为空',
                }
            },
            'base_url': {
                'error_messages': {
                    'invalid': '请输入有效的URL地址'
                }
            }
        }

    def validate_name(self, value):
        """项目名称唯一性校验"""
        instance = self.instance
        current_name = getattr(instance, 'name', None)
        # 忽略大小写 比较
        if instance and value.lower() == current_name.lower():
            return value
        # 忽略大小写
        if Projects.objects.filter(name__iexact=value).exists():
            raise BusinessException(ErrorCode.PROJECT_NAME_EXISTS)
        return value


class GlobalVariableSerialize(serializers.ModelSerializer):
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
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
        model = GlobalVariable
        fields = ('id', 'name', 'value', 'updated_at',
                  'created_at', 'created_by', 'updated_by')
        # 增强字段验证规则
        extra_kwargs = {
            'name': {
                'min_length': 2,
                'max_length': 16,
                'error_messages': {
                    'min_length': '变量名称至少2个字符',
                    'max_length': '变量名称不能超过16个字符',
                    'blank': '项目名称不能为空',
                }
            }
        }

    def validate_name(self, value):
        """变量名称唯一性校验"""
        instance = self.instance
        current_name = getattr(instance, 'name', None)
        # 忽略大小写 比较 | 提交的数据和已存在的数据相同，则直接返回，确保编辑可以为当前名称
        if instance and value.lower() == current_name.lower():
            return value
        # 忽略大小写
        if GlobalVariable.objects.filter(name__iexact=value).exists():
            raise BusinessException(ErrorCode.VARIABLE_NAME_EXISTS)
        return value
