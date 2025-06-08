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
    # interface = serializers.SlugRelatedField(
    #     queryset=InterFace.objects.all(),  # 确保导入Project模型
    #     slug_field='name',
    #     write_only=True,  # 仅在反序列化时生效
    # )
    interface_name = serializers.CharField(
        source='interface.name',
        read_only=True,
        help_text="接口名称"
    )

    class Meta:
        model = TestCase
        fields = '__all__'
        # extra_kwargs = {
        #     'assertions': {'default': list},
        #     'variable_extract': {'default': list},
        #     'body': {'default': dict},
        # }


class SimpleTestCaseSerializer(BaseModelSerializer):
    class Meta:
        model = TestCase
        fields = ['id', 'name']


class SuiteCaseRelationSerializer(serializers.ModelSerializer):
    # case_name = serializers.CharField(source='case.case_name', read_only=True)
    # case_detail = TestCaseSerializer(source='case', read_only=True, help_text='关联的用例详情')

    class Meta:
        model = SuiteCaseRelation
        # fields = ['id', 'case', 'case_name', 'order', 'enabled']
        fields = '__all__'
        extra_kwargs = {
            'case': {'write_only': True}
        }


class TestSuiteSerializer(BaseModelSerializer):
    # 序列化输出时返回case id列表，反序列化时支持通过id列表关联用例
    # cases = serializers.PrimaryKeyRelatedField(
    #     queryset=TestCase.objects.all(),
    #     many=True,
    #     write_only=True,  # 仅在反序列化时生效
    #     help_text="关联用例ID列表"
    # )
    cases = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=True,
        help_text="用例ID列表（带顺序）"
    )
    # cases = serializers.SerializerMethodField(read_only=True)

    # 序列化输出时返回项目名称，反序列化时支持通过名称关联项目对象
    project = serializers.SlugRelatedField(
        queryset=Projects.objects.all(),  # 确保导入Project模型
        slug_field='id',
        # write_only=True,  # 仅在反序列化时生效
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

    # 处理多对多关系保存
    def create(self, validated_data):
        cases = validated_data.pop('cases', [])
        instance = TestSuite.objects.create(**validated_data)
        # suite.cases.set(cases)  # 直接设置多对多关系

        # 批量创建顺序记录
        SuiteCaseRelation.objects.bulk_create([
            SuiteCaseRelation(
                suite=instance,
                case_id=case_id,
                order=idx  # 根据列表顺序生成order
            ) for idx, case_id in enumerate(cases)
        ])
        return instance

    def update(self, instance, validated_data):
        cases = validated_data.pop('cases', None)
        if cases is not None:
            # 删除旧关联
            instance.suitecaserelation_set.all().delete()

            # 创建新关联
            SuiteCaseRelation.objects.bulk_create([
                SuiteCaseRelation(
                    suite=instance,
                    case_id=case_id,
                    order=idx
                ) for idx, case_id in enumerate(cases)
            ])
        return super().update(instance, validated_data)

    def get_execution_status(self, obj):
        """获取套件最新执行记录的状态"""
        # 获取关联的 TestExecution 记录，按执行时间降序取第一条
        latest_execution = obj.testexecution_set.order_by('-started_at').first()
        return latest_execution.status if latest_execution else 'pending'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # 手动添加输出时的cases字段
        data['cases'] = instance.suitecaserelation_set.all().values_list('case_id', flat=True)
        return data


class CaseExecutionSerializer(serializers.ModelSerializer):
    case_name = serializers.CharField(source='case.case_name', read_only=True)
    executed_by = serializers.CharField(source='executed_by.username')
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = CaseExecution
        fields = [
            'id', 'case', 'case_name', 'status',
            'request_data', 'response_data',
            'assertions_result', 'extracted_vars',
            'duration', 'created_at', 'executed_by'
        ]


class TestExecutionSerializer(serializers.ModelSerializer):
    cases = CaseExecutionSerializer(
        'cases',
        many=True,
        read_only=True
    )
    executed_by = serializers.StringRelatedField()
    suite = serializers.CharField(source='suite.name', read_only=True)
    started_at =serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    ended_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    # 计算字段
    pass_rate = serializers.SerializerMethodField()
    total_cases = serializers.SerializerMethodField()
    passed_cases = serializers.SerializerMethodField()

    class Meta:
        model = TestExecution
        fields = [
            'id', 'suite', 'status', 'started_at',
            'ended_at', 'duration', 'executed_by',
            'cases', 'pass_rate', 'total_cases', 'passed_cases'
        ]

    def get_pass_rate(self, obj):
        """计算通过率"""
        total = obj.cases.count()
        if total == 0:
            return 0
        passed = obj.cases.filter(status='passed').count()
        return round(passed / total * 100, 2)

    def get_total_cases(self, obj):
        """获取用例总数"""
        return obj.cases.count()

    def get_passed_cases(self, obj):
        """获取通过用例数"""
        return obj.cases.filter(status='passed').count()

class ExecutionHistorySerializer(serializers.Serializer):
    # 通用字段
    id = serializers.IntegerField(source='s_id', allow_null=True)
    # 通用字段
    record_type = serializers.CharField()
    record_name = serializers.CharField()
    status = serializers.CharField()
    started_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')
    duration = serializers.FloatField(allow_null=True)
    executed_by_username = serializers.CharField()

    # 套件执行特有字段
    suite_total_cases = serializers.IntegerField(allow_null=True, required=False)
    suite_passed_cases = serializers.IntegerField(allow_null=True, required=False)
    suite_execution_id = serializers.IntegerField(allow_null=True, required=False)
    suite_suite_id = serializers.IntegerField(allow_null=True, required=False)

    # 用例执行特有字段
    case_execution_id = serializers.IntegerField(allow_null=True, required=False)
    case_suite_id = serializers.IntegerField(allow_null=True, required=False)
    case_suite_name = serializers.CharField(allow_null=True, required=False)
    case_case_id = serializers.IntegerField(allow_null=True, required=False)
    case_case_name = serializers.CharField(allow_null=True, required=False)

    def to_representation(self, instance):
        """统一字段命名并清理无关字段"""
        data = super().to_representation(instance)

        # 根据类型处理数据
        if data['record_type'] == 'suite':
            # 套件执行记录
            result = {
                'id': data['suite_execution_id'],
                'type': 'suite',
                'name': data['record_name'],
                'status': data['status'],
                'started_at': data['started_at'],
                'duration': data['duration'],
                'executed_by_username': data['executed_by_username'],
                'total_cases': data['suite_total_cases'],
                'passed_cases': data['suite_passed_cases'],
                'suite_id': data['suite_suite_id']
            }
        else:
            # 用例执行记录
            result = {
                'id': data['case_execution_id'],
                'type': 'case',
                'name': data['record_name'],
                'status': data['status'],
                'started_at': data['started_at'],
                'duration': data['duration'],
                'executed_by_username': data['executed_by_username'],
                'suite_id': data['case_suite_id'],
                'suite_name': data['case_suite_name'],
                'case_id': data['case_case_id'],
                'case_name': data['case_case_name']
            }

        return result
