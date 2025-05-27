from common.utils import APIResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import TestSuite, TestExecution, InterFace, TestCase, Module
from .serializers import (TestSuiteSerializer, TestExecutionSerializer,
                          InterFaceSerializer, TestCaseSerializer, ModuleSerializer, AllModuleSerializer,
                          InterFaceIdNameSerializer, SimpleTestCaseSerializer)
from .filter_set import TestCaseFilter, SuiteFilter
from datetime import timezone
from common.error_codes import ErrorCode
from common.handle_test.tasks import async_execute_suite
import logging

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
            # execution.status = 'failed'
            # execution.ended_at = timezone.now()
            # execution.save()
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

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """查询执行状态"""
        execution = self.get_object()
        progress = f"{execution.cases.exclude(status='pending').count()}/{execution.cases.count()}"
        return Response({
            'execution_id': execution.id,
            'status': execution.status,
            'progress': progress
        })
