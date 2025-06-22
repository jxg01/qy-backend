from common.utils import APIResponse
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from ui_case.models import UiTestCase, UiExecution, UiElement
from ui_case.serializers import UiTestCaseSerializer, UiExecutionSerializer, UiElementSerializer
from common.handle_ui_test.ui_tasks import run_ui_test_case
from rest_framework.decorators import action


class UiElementViewSet(viewsets.ModelViewSet):
    queryset = UiElement.objects.all()
    serializer_class = UiElementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.request.query_params.get('project_id')
        if project_id:
            return self.queryset.filter(project_id=project_id)
        return self.queryset


class UiTestCaseViewSet(viewsets.ModelViewSet):
    queryset = UiTestCase.objects.all()
    serializer_class = UiTestCaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.request.query_params.get('project_id')
        if project_id:
            return self.queryset.filter(project_id=project_id)
        return self.queryset

    @action(detail=True, methods=['post'], url_path='run')
    def run_test_case(self, request, pk=None):
        try:
            testcase = self.get_object()
            execution = UiExecution.objects.create(testcase=testcase, status='pending', logs='', screenshots=[], duration=0)
            run_ui_test_case.delay(execution.id)
            return APIResponse("Test case execution started", status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return APIResponse(str(e), status=status.HTTP_400_BAD_REQUEST)


class UiExecutionViewSet(viewsets.ModelViewSet):
    queryset = UiExecution.objects.all()
    serializer_class = UiExecutionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        testcase_id = self.request.query_params.get('testcase_id')
        if testcase_id:
            return self.queryset.filter(testcase_id=testcase_id)
        return self.queryset

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)





