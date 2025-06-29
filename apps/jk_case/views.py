from common.utils import APIResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import TestSuite, TestExecution, InterFace, TestCase, Module, CaseExecution
from .serializers import (TestSuiteSerializer, TestExecutionSerializer,
                          InterFaceSerializer, TestCaseSerializer, ModuleSerializer, AllModuleSerializer,
                          InterFaceIdNameSerializer, SimpleTestCaseSerializer, CaseExecutionSerializer, ExecutionHistorySerializer)
from .filter_set import TestCaseFilter, SuiteFilter
from datetime import datetime
from common.error_codes import ErrorCode
from common.handle_test.tasks import async_execute_suite
from common.handle_test.runcase import execute_case
from common.handle_test.run_interface import execute_interface
from common.exceptions import BusinessException
import logging

from django.db.models import Count, F, Q, Value, CharField

log = logging.getLogger('django')


class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.select_related('project', 'parent_module').prefetch_related('submodules', 'interface')
    # queryset = Module.objects.filter(parent_module__isnull=True)
    serializer_class = ModuleSerializer

    def get_queryset(self):
        # 默认仅返回顶级模块（parent_module=None
        # if self.action == 'partial_update' or self.action == 'destroy' or self.action == 'update' or self.action == 'retrieve':
        if self.action in ('partial_update', 'destroy', 'update', 'retrieve'):
            # 如果是部分更新，返回所有模块
            queryset = Module.objects.all()
        else:
            queryset = Module.objects.filter(parent_module=None)

        # 如果请求中指定了 parent_module_id，返回该父模块的子模块
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = Module.objects.filter(project_id=project_id, parent_module=None)
        return queryset.select_related('project').prefetch_related('submodules')

    def perform_create(self, serializer):
        """自动设置创建人"""
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )

    def perform_update(self, serializer):
        """自动设置更新人"""
        serializer.save(updated_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='rename')
    def rename_module(self, request):
        """重命名模块"""
        module_id = request.data.get('id')
        new_name = request.data.get('name')

        if not module_id or not new_name:
            return APIResponse(
                code=ErrorCode.PARAM_ERROR.code,
                message='缺少必要参数'
            )

        try:
            module = Module.objects.get(id=module_id)
            module.name = new_name
            module.save()
            return APIResponse(message='模块名称更新成功')
        except Module.DoesNotExist:
            return APIResponse(
                code=ErrorCode.PARAM_ERROR.code,
                message='模块不存在'
            )

    @action(detail=False, methods=['get'], url_path='all')
    def all_modules(self, request):
        """获取所有模块"""
        data = request.query_params
        project_id = data.get('project_id')
        if project_id:
            modules = Module.objects.filter(project_id=project_id)
        else:
            modules = Module.objects.all()
        serializer = AllModuleSerializer(modules, many=True)
        return APIResponse(data=serializer.data)


class InterFaceViewSet(viewsets.ModelViewSet):
    queryset = InterFace.objects.all()
    serializer_class = InterFaceSerializer  # 确保已导入 InterFaceCaseSerializer
    permission_classes = [permissions.IsAuthenticated]
    # filterset_fields = ['project', 'case_name']  # 可选字段过滤
    # search_fields = ['case_name', 'url']        # 可选搜索字段

    def perform_create(self, serializer):
        """自动设置创建人"""
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )

    def perform_update(self, serializer):
        """自动设置更新人"""
        serializer.save(updated_by=self.request.user)

    def get_queryset(self):
        project_id = self.request.query_params.get('project_id')
        if project_id:
            return InterFace.objects.filter(
                module__project_id=project_id
            ) if project_id else InterFace.objects.none()
        else:
            return InterFace.objects.all()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # page = self.paginate_queryset(queryset)
        # if page is not None:
        #     serializer = self.get_serializer(page, many=True)
        #     return self.get_paginated_response(serializer.data)

        serializer = InterFaceIdNameSerializer(queryset, many=True)
        return APIResponse(data=serializer.data)

    @action(detail=False, methods=['post'], url_path='run')
    def execute(self, request, pk=None):
        """
        {
            "method": "GET",
            "url": "HTTP://www.baidu.com",
            "headers": {"content-type": "123"},
            "params": {"content-type": "456"},
            "body_type": "raw",
            "data": {"content-type": "789"},
            "body": {"content-type": "666"}
        }
        """
        payload = request.data
        print('payload', payload)

        data = execute_interface(payload)

        return APIResponse(data=data)


class TestCaseViewSet(viewsets.ModelViewSet):
    queryset = TestCase.objects.all().order_by('-id')
    serializer_class = TestCaseSerializer  # 确保已导入 InterFaceCaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    filterset_class = TestCaseFilter
    filterset_fields = ['name']  # 可选字段过滤

    def perform_create(self, serializer):
        """自动设置创建人"""
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )

    def perform_update(self, serializer):
        """自动设置更新人"""
        serializer.save(updated_by=self.request.user)

    def list(self, request, *args, **kwargs):
        project_id = self.request.query_params.get('project_id')
        interface_id = self.request.query_params.get('interface_id')
        case_name = self.request.query_params.get('name')

        # 初始化查询集
        queryset = TestCase.objects.all().order_by('-id')

        # 动态构建过滤条件
        if project_id:
            queryset = queryset.filter(interface__module__project_id=project_id)
        if interface_id:
            queryset = queryset.filter(interface_id=interface_id)
        if case_name:
            queryset = queryset.filter(name__icontains=case_name)  # 模糊匹配

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.serializer_class(queryset, many=True)
        return APIResponse(data=serializer.data)

    @action(detail=False, methods=['get'], url_path='simple-cases')
    def simple_cases(self, request):
        project_id = request.query_params.get('project_id')
        queryset = TestCase.objects.all().order_by('-id')
        if project_id:
            queryset = queryset.filter(interface__module__project_id=project_id)

        serializer = SimpleTestCaseSerializer(queryset, many=True)
        return APIResponse(data=serializer.data)

    @action(detail=True, methods=['post'], url_path='execute')
    def execute(self, request, pk=None):
        """
        request example:
            {"env_url": "http://127.0.0.1:8000"}
        """
        case = self.get_object()
        env_url = request.data.get('env_url')

        if not case.enabled:
            raise BusinessException(ErrorCode.TESTCASE_DISABLED)

        execute_case(case_obj=case, execute_env=env_url, executed_by=request.user)

        return APIResponse({'code': 0, 'message': '执行完成'})

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        """
        request example:

        仅返回最近的10次执行记录
        """
        case_instance = self.get_object()

        queryset = CaseExecution.objects.filter(case=case_instance).order_by('-created_at')[:10]

        serializer = CaseExecutionSerializer(queryset, many=True)

        return APIResponse(data=serializer.data)

class TestSuiteViewSet(viewsets.ModelViewSet):
    queryset = TestSuite.objects.all().order_by('-id')
    serializer_class = TestSuiteSerializer
    permission_classes = [permissions.IsAuthenticated]
    # 自定义模糊搜索 字段
    filterset_class = SuiteFilter

    def perform_create(self, serializer):
        """自动设置创建人"""
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        # 记录修改日志
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='execute')
    def execute(self, request, pk=None):
        """
        Example:
            {"env_url": "http://127.0.0.1:8000"}
        """
        suite = self.get_object()
        env_url = request.data.get('env_url')
        # if not suite.enabled:
        #     raise BusinessException(ErrorCode.TESTSUITE_DISABLED)
        # if not env_url:
        #     raise BusinessException(ErrorCode.TESTSUITE_DISABLED)
        if suite.cases.count() == 0:
            raise BusinessException(ErrorCode.SUITE_RELATED_CASE_NOT_EXISTS)
        if suite.cases.filter(enabled=False).count() == suite.cases.count():
            raise BusinessException(ErrorCode.SUITE_RELATED_CASE_ALL_DISABLED)

        # 创建新的执行记录
        execution = TestExecution.objects.create(
            suite=suite,
            status='pending',
            executed_by=request.user
        )
        try:
            # 触发异步任务
            async_execute_suite.delay(execution.id, request.user.id, env_url)
            return Response(
                {'execution_id': execution.id, 'status': '任务已提交'},
                status=status.HTTP_202_ACCEPTED
            )
        except Exception as e:
            # 回滚执行记录状态
            execution.status = 'failed'
            execution.ended_at = datetime.now()
            execution.save()
            return Response(
                {'error': f'任务提交失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TestExecutionViewSet(viewsets.ModelViewSet):
    queryset = TestExecution.objects.all().order_by('-id')
    serializer_class = TestExecutionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # 搜索
        query_set = TestExecution.objects.all().order_by('-id')
        suite = self.request.query_params.get('suite')
        if suite:
            query_set = TestExecution.objects.filter(suite__id=suite).order_by('-id')[:10]
        return query_set


class CaseExecutionViewSet(viewsets.ModelViewSet):
    queryset = CaseExecution.objects.all()
    serializer_class = CaseExecutionSerializer
    permission_classes = [permissions.IsAuthenticated]


class ExecutionHistoryViewSet(viewsets.ModelViewSet):
    serializer_class = ExecutionHistorySerializer
    http_method_names = ['get']  # 只允许 GET 请求

    def get_queryset(self):
        # 返回空查询集，因为我们重写了 list 方法
        return TestExecution.objects.none()

    def list(self, request, *args, **kwargs):
        # 获取查询参数
        limit = request.query_params.get('limit')
        exec_type = request.query_params.get('type')
        status = request.query_params.get('status')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        # 准备套件执行查询集
        suite_qs = TestExecution.objects.select_related('suite', 'executed_by')

        # 准备用例执行查询集
        case_qs = CaseExecution.objects.select_related(
            'case', 'execution', 'execution__suite', 'execution__executed_by'
        ).filter(execution__isnull=True)

        # 应用类型过滤
        if exec_type == 'suite':
            case_qs = case_qs.none()
        elif exec_type == 'case':
            suite_qs = suite_qs.none()

        # 应用状态过滤
        if status:
            suite_qs = suite_qs.filter(status=status)
            case_qs = case_qs.filter(status=status)

        # 应用日期范围过滤
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()

                suite_qs = suite_qs.filter(started_at__date__range=[start, end])
                case_qs = case_qs.filter(created_at__date__range=[start, end])
            except ValueError:
                pass

        # 获取套件执行记录 - 使用 "suite_" 前缀
        suite_executions = suite_qs.annotate(
            record_type=Value('suite', output_field=CharField()),
            record_name=F('suite__name'),
            executed_by_username=F('executed_by_id__username'),
            suite_total_cases=Count('cases', distinct=True),
            suite_passed_cases=Count('cases', filter=Q(cases__status='passed'), distinct=True),

            # 使用唯一前缀避免冲突
            suite_execution_id=F('id'),
            suite_suite_id=F('suite_id')
        ).values(
            'record_type', 'record_name', 'status', 'started_at',
            'duration', 'executed_by_username',
            'suite_total_cases', 'suite_passed_cases',
            'suite_execution_id', 'suite_suite_id'
        )

        # 获取用例执行记录 - 使用 "case_" 前缀
        case_executions = case_qs.annotate(
            record_type=Value('case', output_field=CharField()),
            record_name=F('case__name'),
            executed_by_username=F('executed_by_id__username'),
            started_at=F('created_at'),

            # 使用唯一前缀避免冲突
            case_execution_id=F('id'),
            case_suite_id=F('execution_id'),
            case_suite_name=F('execution__suite__name'),
            case_case_id=F('case_id'),
            case_case_name=F('case__name')
        ).values(
            'record_type', 'record_name', 'status', 'started_at',
            'duration', 'executed_by_username',
            'case_execution_id', 'case_suite_id',
            'case_suite_name', 'case_case_id', 'case_case_name'
        )

        # 合并并排序
        combined = list(suite_executions) + list(case_executions)
        combined.sort(key=lambda x: x['started_at'], reverse=True)
        if limit:
            combined = combined[:int(limit)]  # 限制返回数量

        # 分页处理
        page = self.paginate_queryset(combined)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(combined, many=True)
        return APIResponse(serializer.data)



