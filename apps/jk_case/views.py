from common.utils import APIResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import TestSuite, TestExecution, InterFace, TestCase, Module, CaseExecution
from .serializers import (TestSuiteSerializer, TestExecutionSerializer,
                          InterFaceSerializer, TestCaseSerializer, ModuleSerializer, AllModuleSerializer,
                          InterFaceIdNameSerializer, SimpleTestCaseSerializer, CaseExecutionSerializer, ExecutionHistorySerializer)
from .filter_set import TestCaseFilter, SuiteFilter
from datetime import timezone
from common.error_codes import ErrorCode
from common.handle_test.tasks import async_execute_suite
from common.handle_test.runcase import execute_case
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

    # @action(detail=True, methods=['post'], url_path='add-cases')
    # def add_cases(self, request, pk=None):
    #     """批量添加用例到测试套件
    #     request body example:
    #         {"case_ids": [1, 2, 3]}
    #     """
    #     suite = self.get_object()
    #     data = request.data
    #
    #     # 验证请求数据格式
    #     case_ids = data.get('case_ids', [])
    #     if not isinstance(case_ids, list):
    #         d = {
    #             'code': ErrorCode.PARAM_ERROR.code,
    #             'message': '请求参数应为用例列表',
    #         }
    #         return Response(d, status=400)
    #
    #     # 处理批量创建
    #     relations_to_create = []
    #     failed_list = []
    #
    #     for case_id in case_ids:
    #         # 验证用例是否存在
    #         try:
    #             case = TestCase.objects.get(id=case_id)
    #             # 检查重复添加
    #             if SuiteCaseRelation.objects.filter(suite_id=suite, case_id=case).exists():
    #                 failed_list.append(case_id)
    #                 continue
    #             max_order = SuiteCaseRelation.objects.filter(suite_id=suite)
    #             local_order = 0
    #             if max_order:
    #                 local_order = max_order.values('order').order_by('-order')[0]['order'] + 1
    #
    #             relations_to_create.append(SuiteCaseRelation(
    #                 suite=suite,
    #                 case=case,
    #                 order=local_order if local_order else 1,
    #             ))
    #         except TestCase.DoesNotExist:
    #             failed_list.append(case_id)
    #     # 批量创建关系
    #     if relations_to_create:
    #         SuiteCaseRelation.objects.bulk_create(relations_to_create)
    #
    #     # 构建响应
    #     response_data = {
    #         "success_count": len(relations_to_create),
    #         "failed_count": len(failed_list)
    #     }
    #     return Response(data=response_data)
    #
    # @action(detail=True, methods=['get'], url_path='relation-cases')
    # def relation_cases(self, request, pk=None):
    #     """获取套件的用例"""
    #     suite = self.get_object()
    #     # 获取套件关联的用例关系对象
    #     relations = SuiteCaseRelation.objects.filter(suite=suite)
    #
    #     # 使用嵌套序列化器返回详细信息
    #     serializer = SuiteCaseRelationSerializer(
    #         relations,
    #         many=True,
    #         context={'request': request}
    #     )
    #
    #     return Response(serializer.data)
    #
    # @action(detail=True, methods=['post'], url_path='remove-cases')
    # def remove_cases(self, request, pk=None):
    #     """批量解绑测试套件关联的用例
    #     request body example:
    #         {"case_ids": [1, 2, 3]}
    #     """
    #     suite = self.get_object()
    #     data = request.data
    #
    #     # 验证请求数据格式
    #     case_ids = data.get('case_ids', [])
    #     if not isinstance(case_ids, list):
    #         data = {
    #             'code': ErrorCode.PARAM_ERROR.code,
    #             'message': '请求参数应为用例列表',
    #         }
    #         return Response(data, status=400)
    #     # 过滤有效关联记录
    #     relations = SuiteCaseRelation.objects.filter(
    #         suite=suite,
    #         case_id__in=case_ids
    #     )
    #
    #     # 执行删除操作
    #     deleted_count, _ = relations.delete()
    #
    #     # 构建响应
    #     response_data = {
    #         "success_count": deleted_count,
    #         "failed_count": len(case_ids) - deleted_count
    #     }
    #     return Response(data=response_data)
    #
    # @action(detail=True, methods=['post'], url_path='reorder-cases')
    # def reorder_cases(self, request, pk=None):
    #     """调整用例顺序
    #     request body example:
    #         [{"case_id": 1, "order": 1}, {"case_id": 2, "order": 2}]
    #     """
    #     suite = self.get_object()
    #     data = request.data
    #     relations_to_update = []
    #     for case_info in data:
    #         try:
    #             case = TestCase.objects.get(id=case_info['case_id'])
    #             relation_record_id = SuiteCaseRelation.objects.get(suite_id=suite, case_id=case).id
    #             relations_to_update.append(
    #                 SuiteCaseRelation(
    #                     id=relation_record_id,
    #                     order=case_info['order'],
    #                 )
    #             )
    #         except TestCase.DoesNotExist:
    #             return Response({
    #                 'code': ErrorCode.PARAM_ERROR.code,
    #                 'message': f"用例 {case_info['case_id']} 不存在",
    #             }, status=400)
    #         except SuiteCaseRelation.DoesNotExist:
    #             return Response({
    #                 'code': ErrorCode.PARAM_ERROR.code,
    #                 'message': f"用例 {case_info['case_id']} 不在套件 {suite.name} 中",
    #             }, status=400)
    #     SuiteCaseRelation.objects.bulk_update(relations_to_update, ['order'])
    #     return Response({'status': 'success'})

    @action(detail=True, methods=['post'], url_path='execute')
    def execute(self, request, pk=None):
        suite = self.get_object()
        # 创建新的执行记录
        execution = TestExecution.objects.create(
            suite=suite,
            status='pending',
            executed_by=request.user
        )
        try:
            # 触发异步任务
            async_execute_suite.delay(execution.id)
            return Response(
                {'execution_id': execution.id, 'status': '任务已提交'},
                status=status.HTTP_202_ACCEPTED
            )
        except Exception as e:
            # 回滚执行记录状态
            execution.status = 'failed'
            execution.ended_at = timezone.now()
            execution.save()
            return Response(
                {'error': f'任务提交失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TestExecutionViewSet(viewsets.ModelViewSet):
    queryset = TestExecution.objects.all()
    serializer_class = TestExecutionSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """触发异步执行测试套件"""
        # 获取关联的测试套件
        suite = self.get_object()

        # 创建新的执行记录
        execution = TestExecution.objects.create(
            suite=suite,
            status='pending',
            executed_by=request.user
        )

        try:
            # 触发异步任务
            async_execute_suite.delay(execution.id)
            return Response(
                {'execution_id': execution.id, 'status': '任务已提交'},
                status=status.HTTP_202_ACCEPTED
            )
        except Exception as e:
            # 回滚执行记录状态
            execution.status = 'failed'
            execution.ended_at = timezone.now()
            execution.save()
            return Response(
                {'error': f'任务提交失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



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

    # def list(self, request, *args, **kwargs):
    #     # 获取套件执行记录
    #     suite_executions = TestExecution.objects.annotate(
    #         type=Value('suite'),
    #         name=F('suite__name'),
    #         executed_by_username=F('executed_by__username'),
    #         total_cases=Count('cases', distinct=True),
    #         passed_cases=Count('cases', filter=Q(cases__status='passed'), distinct=True)
    #     ).values(
    #         'id', 'type', 'name', 'status', 'started_at',
    #         'duration', 'executed_by_username',
    #         'total_cases', 'passed_cases'
    #     )
    #
    #     # 获取用例执行记录
    #     case_executions = CaseExecution.objects.annotate(
    #         type=Value('case'),
    #         name=F('case__name'),
    #         suite_id=F('execution_id'),
    #         suite_name=F('execution__suite__name'),
    #         case_id=F('case_id'),
    #         case_name=F('case__name'),
    #         executed_by_username=F('execution__executed_by__username'),
    #         started_at=F('created_at')
    #     ).values(
    #         'id', 'type', 'name', 'status', 'started_at',
    #         'duration', 'executed_by_username',
    #         'suite_id', 'suite_name', 'case_id', 'case_name'
    #     )
    #
    #     # 合并并排序
    #     combined = list(suite_executions) + list(case_executions)
    #     combined.sort(key=lambda x: x['started_at'], reverse=True)
    #
    #     # 分页处理
    #     page = self.paginate_queryset(combined)
    #     serializer = self.get_serializer(page, many=True)
    #     return self.get_paginated_response(serializer.data)
    def list(self, request, *args, **kwargs):
        # 获取查询参数
        exec_type = request.query_params.get('type')
        status = request.query_params.get('status')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        # 准备套件执行查询集
        suite_qs = TestExecution.objects.select_related('suite', 'executed_by')

        # 准备用例执行查询集
        case_qs = CaseExecution.objects.select_related(
            'case', 'execution', 'execution__suite', 'execution__executed_by'
        )

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
                start = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
                end = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()

                suite_qs = suite_qs.filter(started_at__date__range=[start, end])
                case_qs = case_qs.filter(created_at__date__range=[start, end])
            except ValueError:
                pass

        # 获取套件执行记录 - 使用 "suite_" 前缀
        suite_executions = suite_qs.annotate(
            record_type=Value('suite', output_field=CharField()),
            record_name=F('suite__name'),
            executed_by_username=F('executed_by__username'),
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
            executed_by_username=F('execution__executed_by__username'),
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

        # 分页处理
        page = self.paginate_queryset(combined)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(combined, many=True)
        return APIResponse(serializer.data)



