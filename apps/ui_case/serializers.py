from rest_framework import serializers
from ui_case.models import (UiElement, UiTestCase, UiExecution)


class UiElementSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    updated_by = serializers.CharField(source='updated_by.username', read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = UiElement
        fields = '__all__'


class UiTestCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = UiTestCase
        fields = '__all__'


class UiExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UiExecution
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['testcase_name'] = instance.testcase.name
        return representation

