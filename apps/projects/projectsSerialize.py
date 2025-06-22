from rest_framework import serializers
from projects.models import Projects, GlobalVariable, ProjectEnvs, PythonCode, DBConfig
from common.error_codes import ErrorCode
from common.exceptions import BusinessException
import django_filters
from jk_case.serializers import ModuleSerializer


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


class DBConfigSerialize(serializers.ModelSerializer):
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
        model = DBConfig
        fields = '__all__'


class ProjectEnvsSerialize(serializers.ModelSerializer):
    db_config = serializers.SerializerMethodField()
    db_info = DBConfigSerialize(read_only=True, source='db_config')


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
        model = ProjectEnvs
        fields = '__all__'
        ordering = ['-id']

    def get_db_config(self, obj):
        """获取数据库配置"""
        db_config = obj.id
        db_exists = DBConfig.objects.filter(env=db_config).exists()
        if db_exists:
            return 1
        return 0


class ProjectsSerialize(serializers.ModelSerializer):
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
    envs = ProjectEnvsSerialize(many=True, read_only=True)

    # modules = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Projects
        # fields = ('id', 'name', 'description', 'updated_by', 'updated_at', 'created_at', 'created_by', 'envs')
        fields = '__all__'
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

    def get_modules(self, obj):
        # 预取直接子模块（parent_module=None）及其递归子模块
        top_level_modules = obj.modules.filter(parent_module=None)
        return ModuleSerializer(top_level_modules, many=True, context=self.context).data


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


class PythonCodeSerialize(serializers.ModelSerializer):
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
        model = PythonCode
        fields = '__all__'
        # 增强字段验证规则
        extra_kwargs = {
            'name': {
                'min_length': 2,
                'max_length': 16,
                'error_messages': {
                    'min_length': '变量名称至少2个字符',
                    'max_length': '��量名称不能超过16个字符',
                    'blank': '项目名称不能为空',
                }
            }
        }


