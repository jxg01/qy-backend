from rest_framework import serializers
from .models import TestSuite, SuiteCaseRelation, InterFace, TestExecution, CaseExecution, TestCase, Module
from projects.models import Projects


class BaseModelSerializer(serializers.ModelSerializer):
    """ 基类序列化器 """
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_by = serializers.CharField(
        source='updated_by.username',
        read_only=True,
        help_text="更新人"
    )
    created_by = serializers.CharField(
        source='created_by.username',
        read_only=True,
        help_text="创建人"
    )


class InterFaceSerializer(BaseModelSerializer):
    # get_ field_name _display
    # 这个写法获取 choice 对应的值
    # method_display = serializers.CharField(
    #     source='get_method_display',
    #     read_only=True
    # )

    class Meta:
        model = InterFace
        fields = '__all__'
        # extra_kwargs = {
        #     'headers': {'default': dict},
        #     'body': {'default': dict},
        #     'assertions': {'default': list},
        #     'variable_extract': {'default': list},
        # }


class InterFaceIdNameSerializer(BaseModelSerializer):
    class Meta:
        model = InterFace
        fields = ['id', 'name']


class ModuleSerializer(BaseModelSerializer):
    # 递归序列化子模块
    children = serializers.SerializerMethodField()
    # 关联接口
    interface = InterFaceSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        # fields = ['id', 'name', 'submodules', 'interface']
        fields = '__all__'

    def get_children(self, obj):
        # # 获取直接子模块并按 order 排序
        # children = obj.submodules.all().order_by('order')
        children = obj.submodules.all()
        return ModuleSerializer(children, many=True, context=self.context).data


class AllModuleSerializer(BaseModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'name']


class TestCaseSerializer(BaseModelSerializer):
    # 序列化输出时返回项目名称，反序列化时支持通过名称关联项目对象
    interface = serializers.SlugRelatedField(
        queryset=InterFace.objects.all(),  # 确保导入Project模型
        slug_field='name',
        write_only=True,  # 仅在反序列化时生效
    )
    interface_name = serializers.CharField(
        source='interface.name',
        read_only=True,
        help_text="接口名称"
    )

    class Meta:
        model = TestCase
        fields = '__all__'
        extra_kwargs = {
            'assertions': {'default': list},
            'variable_extract': {'default': list},
            'body': {'default': dict},
        }


class SuiteCaseRelationSerializer(serializers.ModelSerializer):
    # case_name = serializers.CharField(source='case.case_name', read_only=True)
    case_detail = TestCaseSerializer(source='case', read_only=True, help_text='关联的用例详情')

    class Meta:
        model = SuiteCaseRelation
        # fields = ['id', 'case', 'case_name', 'order', 'enabled']
        fields = '__all__'
        extra_kwargs = {
            'case': {'write_only': True}
        }


class TestSuiteSerializer(BaseModelSerializer):
    cases = SuiteCaseRelationSerializer(
        source='suitecaserelation_set',
        many=True,
        read_only=True
    )
    # 序列化输出时返回项目名称，反序列化时支持通过名称关联项目对象
    project = serializers.SlugRelatedField(
        queryset=Projects.objects.all(),  # 确保导入Project模型
        slug_field='name',
        write_only=True,  # 仅在反序列化时生效
    )
    project_name = serializers.CharField(
        source='project.name',
        read_only=True,  # 仅在序列化输出时生效
        help_text="关联项目名称"
    )
    # 新增字段：返回最新执行状态
    execution_status = serializers.SerializerMethodField(
        help_text="最新测试执行状态",
        read_only=True,
        default='success',
        source='get_execution_status'
    )

    class Meta:
        model = TestSuite
        fields = '__all__'

    def get_execution_status(self, obj):
        """获取套件最新执行记录的状态"""
        # 获取关联的 TestExecution 记录，按执行时间降序取第一条
        latest_execution = obj.testexecution_set.order_by('-started_at').first()
        return latest_execution.status if latest_execution else 'pending'



class CaseExecutionSerializer(serializers.ModelSerializer):
    case_name = serializers.CharField(source='case.case_name', read_only=True)

    class Meta:
        model = CaseExecution
        fields = [
            'id', 'case', 'case_name', 'status',
            'request_data', 'response_data',
            'assertions_result', 'extracted_vars',
            'duration', 'created_at'
        ]


class TestExecutionSerializer(serializers.ModelSerializer):
    cases = CaseExecutionSerializer(
        source='caseexecution_set',
        many=True,
        read_only=True
    )
    executed_by = serializers.StringRelatedField()

    class Meta:
        model = TestExecution
        fields = [
            'id', 'suite', 'status', 'started_at',
            'ended_at', 'duration', 'executed_by', 'cases'
        ]
