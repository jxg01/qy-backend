from rest_framework import serializers
from ui_case.models import (UiElement, UiTestCase, UiExecution)


class UiElementSerializer(serializers.ModelSerializer):
    class Meta:
        model = UiElement
        fields = '__all__'


class UiTestCaseSerializer(serializers.ModelSerializer):
    steps = serializers.JSONField()

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

