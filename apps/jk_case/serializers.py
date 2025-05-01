from rest_framework import serializers
from .models import TestSuite, SuiteCaseRelation, InterFace, TestExecution, CaseExecution, TestCase
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
        extra_kwargs = {
            'headers': {'default': dict},
            'body': {'default': dict},
            'assertions': {'default': list},
            'variable_extract': {'default': list},
        }


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

    class Meta:
        model = TestSuite
        fields = '__all__'


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
