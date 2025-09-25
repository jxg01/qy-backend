from rest_framework import serializers
from ui_case.models import (UiElement, UiTestCase, UiExecution, UiTestModule, UiTestFile)
from common.exceptions import BusinessException
from common.error_codes import ErrorCode


class SimpleUiElementSerializer(serializers.ModelSerializer):
    class Meta:
        model = UiElement
        fields = ['id', 'name', 'locator_type', 'locator_value']


class UiElementSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    updated_by = serializers.CharField(source='updated_by.username', read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = UiElement
        fields = '__all__'

    def validate_name(self, value):
        instance = self.instance
        current_name = getattr(instance, 'name', None)
        # 忽略大小写 比较
        if instance and value.lower() == current_name.lower():
            return value
        if not value:
            raise BusinessException(ErrorCode.UI_ELEMENT_NAME_EMPTY)
        if UiElement.objects.filter(name__iexact=value, project=self.context['request'].data.get('project')).exists():
            raise BusinessException(ErrorCode.UI_ELEMENT_NAME_EXISTS)
        return value

    def validate_locator_value(self, value):
        instance = self.instance
        current_value = getattr(instance, 'locator_value', None)
        # 忽略大小写 比较
        if instance and value.lower() == current_value.lower():
            return value
        if not value:
            raise BusinessException(ErrorCode.UI_ELEMENT_LOCATOR_VALUE_EMPTY)
        if UiElement.objects.filter(locator_value__iexact=value,
                                    project=self.context['request'].data.get('project')).exists():
            raise BusinessException(ErrorCode.UI_ELEMENT_LOCATOR_EXISTS)
        return value


class UiTestCaseSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    updated_by = serializers.CharField(source='updated_by.username', read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = UiTestCase
        fields = '__all__'

    def validate_name(self, value):
        instance = self.instance
        current_name = getattr(instance, 'name', None)
        print('current_name => ', current_name)
        # 忽略大小写 比较
        if instance and value.lower() == current_name.lower():
            return value
        if not value:
            raise BusinessException(ErrorCode.UI_TESTCASE_NAME_EMPTY)
        if UiTestCase.objects.filter(name__iexact=value).exists():
            raise BusinessException(ErrorCode.UI_TESTCASE_NAME_EXISTS)
        return value


class UiTestModuleSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    updated_by = serializers.CharField(source='updated_by.username', read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    cases = UiTestCaseSerializer(source='uitestcase_set', many=True, read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True, allow_null=True)
    children = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UiTestModule
        fields = '__all__'
        extra_kwargs = {
            'parent': {'required': False, 'allow_null': True}
        }

    def get_children(self, obj):
        """直接递归获取当前模块的所有子模块"""
        return UiTestModuleSerializer(obj.children.all(), many=True, context=self.context).data

    def validate_name(self, value):
        instance = self.instance
        current_name = getattr(instance, 'name', None)
        # Ignore case comparison
        if instance and value.lower() == current_name.lower():
            return value
        if not value:
            raise BusinessException(ErrorCode.UI_ELEMENT_NAME_EMPTY)

        # 获取项目ID和父模块ID
        project_id = self.context['request'].data.get('project')
        parent_id = self.context['request'].data.get('parent')

        if not project_id:
            if self.instance:
                project_id = self.instance.project.id
                if parent_id is None:
                    parent_id = self.instance.parent.id if self.instance.parent else None
            else:
                raise BusinessException(ErrorCode.PROJECT_ID_MISSING)

        # 检查同一项目和父模块下是否存在同名模块
        queryset = UiTestModule.objects.filter(project_id=project_id, name__iexact=value)
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        else:
            queryset = queryset.filter(parent__isnull=True)

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)

        if queryset.exists():
            raise BusinessException(ErrorCode.UI_ELEMENT_NAME_EXISTS)

        return value

    def validate_parent(self, value):
        """验证父模块的有效性"""
        if value:
            project_id = self.context['request'].data.get('project')
            if not project_id:
                if self.instance:
                    project_id = self.instance.project.id
                else:
                    raise BusinessException(ErrorCode.PROJECT_ID_MISSING)

            # 确保父模块属于同一个项目
            if value.project.id != int(project_id):
                raise BusinessException(ErrorCode.PARENT_MODULE_NOT_IN_SAME_PROJECT)

            # 防止循环引用
            current_module = self.instance
            if current_module:
                ancestor = value
                while ancestor:
                    if ancestor.id == current_module.id:
                        raise BusinessException(ErrorCode.CIRCULAR_REFERENCE_ERROR)
                    ancestor = ancestor.parent

        return value


class UiExecutionSerializer(serializers.ModelSerializer):
    # screenshot_url = serializers.SerializerMethodField()
    executed_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    executed_by = serializers.CharField(source='executed_by.username', read_only=True)

    class Meta:
        model = UiExecution
        fields = '__all__'
        # fields = ['id', 'status', 'steps_log', 'screenshot_url', 'duration', 'browser_info', 'executed_at', 'executed_by']

    # def get_screenshot_url(self, obj):
    #     return obj.screenshot.url if obj.screenshot else None

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['testcase_name'] = instance.testcase.name
        return representation


class UiTestFileSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.CharField(source='uploaded_by.username', read_only=True)
    uploaded_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    file_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UiTestFile
        fields = '__all__'
        # fields = ['file', 'id', 'name', 'file_name', 'description', 'uploaded_by', 'uploaded_at']

    def get_file_name(self, obj):
        return obj.file.name if obj.file else None
        # return obj.file.path if obj.file else None
