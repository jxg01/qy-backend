from common.utils import APIResponse
from rest_framework import viewsets, permissions, status
from ui_case.models import UiTestCase, UiExecution, UiElement, UiTestModule, UiTestFile
from ui_case.serializers import (UiTestCaseSerializer, UiExecutionSerializer,
                                 UiElementSerializer, UiTestModuleSerializer,
                                 SimpleUiElementSerializer, UiTestFileSerializer)
from common.handle_ui_test.ui_tasks import run_ui_test_case
from rest_framework.decorators import action
from django.db.models import Q
import logging
from common.exceptions import BusinessException
from common.error_codes import ErrorCode

log = logging.getLogger('django')


class UiElementViewSet(viewsets.ModelViewSet):
    queryset = UiElement.objects.all()
    serializer_class = UiElementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.request.query_params.get('project_id')
        # 搜索name ｜ 元素值
        name = self.request.query_params.get('name')
        locator_type = self.request.query_params.get('locator_type')

        # 初始化查询集
        queryset = UiElement.objects.all().order_by('-id')

        # 动态构建过滤条件
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if name:
            queryset = queryset.filter(Q(name__icontains=name) | Q(page__icontains=name))
        if locator_type:
            queryset = queryset.filter(locator_type=locator_type)  # 模糊匹配

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=False, methods=['get'], url_path='get-pages')
    def get_pages(self, request):
        project_id = request.query_params.get('project_id')
        if not project_id:
            return APIResponse("Project ID is required", status=status.HTTP_400_BAD_REQUEST)

        pages = self.queryset.filter(project_id=project_id).values_list('page', flat=True).order_by('page').distinct()
        return APIResponse({"pages": list(pages)}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='simple-elements')
    def get_simple_elements(self, request):

        project_id = request.query_params.get('project_id')
        if not project_id:
            return APIResponse("Project ID is required", status=status.HTTP_400_BAD_REQUEST)

        queryset = self.queryset.filter(project_id=project_id)
        serializer = SimpleUiElementSerializer(queryset, many=True)
        # transformed_data = [
        #     {
        #         "name": item["name"],
        #         "element": {
        #             "locator_type": item["locator_type"],
        #             "locator_value": item["locator_value"]
        #         }
        #     }
        #     for item in serializer.data
        # ]
        return APIResponse(serializer.data, status=status.HTTP_200_OK)



class UiTestModuleViewSet(viewsets.ModelViewSet):
    queryset = UiTestModule.objects.all()
    serializer_class = UiTestModuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.request.query_params.get('project_id')
        queryset = UiTestModule.objects.all().order_by('-created_at')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class UiTestCaseViewSet(viewsets.ModelViewSet):
    queryset = UiTestCase.objects.all()
    serializer_class = UiTestCaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def get_queryset(self):
        project_id = self.request.query_params.get('project_id')
        if project_id:
            return self.queryset.filter(project_id=project_id)
        return self.queryset

    @action(detail=True, methods=['post'], url_path='run')
    def run_test_case(self, request, pk=None):
        """
        接口参数：{"browser_info": "chromium"}
        """
        try:
            browser_info = request.data.get('browser_type', 'chromium')
            headless = request.data.get('headless', True)
            testcase = self.get_object()
            execution = UiExecution.objects.create(
                testcase=testcase, status='running', steps_log='', screenshot='',
                duration=0, browser_info=browser_info, executed_by=request.user
            )
            run_ui_test_case.delay(execution.id, browser_info, is_headless=headless)
            return APIResponse("测试任务已开始", status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            log.info(f'失败的任务：{e}')
            return APIResponse(str(e), status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='run-selected')
    def run_selected(self, request, pk=None):
        """
        接口参数：{"browser_info": "chromium", "case_ids": [1, 2]}
        chromium（Chrome/Edge基础）
        webKit（Safari基础）
        firefox
        """
        # try:
        browser_info = request.data.get('browser_type', 'chromium')
        headless = request.data.get('headless', True)
        case_ids = request.data.get('case_ids', [])
        log.info(f'接收到的用例ID列表：{case_ids} | 浏览器信息：{browser_info} | 是否无头模式：{headless}')
        if not browser_info:
            browser_info = 'chromium'
        if not case_ids:
            raise BusinessException(ErrorCode.SELECTED_CASES_ID_IS_EMPTY)
        testcases = UiTestCase.objects.filter(id__in=case_ids)
        for testcase in testcases:
            execution = UiExecution.objects.create(
                testcase=testcase, status='running', steps_log='', screenshot='',
                duration=0, browser_info=browser_info, executed_by=request.user
            )
            run_ui_test_case.delay(execution.id, browser_info, is_headless=headless)
            print('提交任务的用例：', testcase.name)
        return APIResponse("测试任务已开始", status=status.HTTP_202_ACCEPTED)
        # except Exception as e:
        #     log.info(f'失败的任务：{e}')
        #     return APIResponse(str(e), status=status.HTTP_400_BAD_REQUEST)


class UiExecutionViewSet(viewsets.ModelViewSet):
    queryset = UiExecution.objects.all()
    serializer_class = UiExecutionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        executed_by = self.request.query_params.get('executed_by')
        case_name = self.request.query_params.get('case_name')
        case_status = self.request.query_params.get('case_status')

        if case_status:
            self.queryset = self.queryset.filter(status=case_status)
        if case_name:
            self.queryset = self.queryset.filter(testcase__name__icontains=case_name)

        if executed_by:
            self.queryset = self.queryset.filter(executed_by__username__icontains=executed_by)

        return self.queryset

    # def retrieve(self, request, *args, **kwargs):
    #     instance = self.get_object()
    #     serializer = self.get_serializer(instance)
    #     return Response(serializer.data)


class UiTestFileViewSet(viewsets.ModelViewSet):
    queryset = UiTestFile.objects.all()
    serializer_class = UiTestFileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


