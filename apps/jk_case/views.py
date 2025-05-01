from common.utils import APIResponse
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import TestSuite, SuiteCaseRelation, TestExecution, InterFace, TestCase
from .serializers import TestSuiteSerializer, SuiteCaseRelationSerializer, TestExecutionSerializer, InterFaceSerializer, TestCaseSerializer
from datetime import timezone
from common.error_codes import ErrorCode


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


class TestCaseViewSet(viewsets.ModelViewSet):
    queryset = TestCase.objects.all()
    serializer_class = TestCaseSerializer  # 确保已导入 InterFaceCaseSerializer
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


class TestSuiteViewSet(viewsets.ModelViewSet):
    queryset = TestSuite.objects.all()
    serializer_class = TestSuiteSerializer
    permission_classes = [permissions.IsAuthenticated]
    # filterset_fields = ['project', 'name']
    # search_fields = ['name', 'description']

    def perform_create(self, serializer):
        """自动设置创建人"""
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        # 记录修改日志
        instance = serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='add-cases')
    def add_cases(self, request, pk=None):
        """批量添加用例到测试套件
        request body example:
            {"case_ids": [1, 2, 3]}
        """
        suite = self.get_object()
        data = request.data

        # 验证请求数据格式
        case_ids = data.get('case_ids', [])
        if not isinstance(case_ids, list):
            d = {
                'code': ErrorCode.PARAM_ERROR.code,
                'message': '请求参数应为用例列表',
            }
            return Response(d, status=400)

        # 处理批量创建
        relations_to_create = []
        failed_list = []

        for case_id in case_ids:
            # 验证用例是否存在
            try:
                case = TestCase.objects.get(id=case_id)
                # 检查重复添加
                if SuiteCaseRelation.objects.filter(suite_id=suite, case_id=case).exists():
                    failed_list.append(case_id)
                    continue
                max_order = SuiteCaseRelation.objects.filter(suite_id=suite)
                local_order = 0
                if max_order:
                    local_order = max_order.values('order').order_by('-order')[0]['order'] + 1

                relations_to_create.append(SuiteCaseRelation(
                    suite=suite,
                    case=case,
                    order=local_order if local_order else 1,
                ))
            except TestCase.DoesNotExist:
                failed_list.append(case_id)
        # 批量创建关系
        if relations_to_create:
            SuiteCaseRelation.objects.bulk_create(relations_to_create)

        # 构建响应
        response_data = {
            "success_count": len(relations_to_create),
            "failed_count": len(failed_list)
        }
        return Response(data=response_data)

    @action(detail=True, methods=['get'], url_path='relation-cases')
    def relation_cases(self, request, pk=None):
        """获取套件的用例"""
        suite = self.get_object()
        # 获取套件关联的用例关系对象
        relations = SuiteCaseRelation.objects.filter(suite=suite)

        # 使用嵌套序列化器返回详细信息
        serializer = SuiteCaseRelationSerializer(
            relations,
            many=True,
            context={'request': request}
        )

        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='remove-cases')
    def remove_cases(self, request, pk=None):
        """批量解绑测试套件关联的用例
        request body example:
            {"case_ids": [1, 2, 3]}
        """
        suite = self.get_object()
        data = request.data

        # 验证请求数据格式
        case_ids = data.get('case_ids', [])
        if not isinstance(case_ids, list):
            data = {
                'code': ErrorCode.PARAM_ERROR.code,
                'message': '请求参数应为用例列表',
            }
            return Response(data, status=400)
        # 过滤有效关联记录
        relations = SuiteCaseRelation.objects.filter(
            suite=suite,
            case_id__in=case_ids
        )

        # 执行删除操作
        deleted_count, _ = relations.delete()

        # 构建响应
        response_data = {
            "success_count": deleted_count,
            "failed_count": len(case_ids) - deleted_count
        }
        return Response(data=response_data)

    @action(detail=True, methods=['post'], url_path='reorder-cases')
    def reorder_cases(self, request, pk=None):
        """调整用例顺序
        request body example:
            [{"case_id": 1, "order": 1}, {"case_id": 2, "order": 2}]
        """
        suite = self.get_object()
        data = request.data
        relations_to_update = []
        for case_info in data:
            try:
                case = TestCase.objects.get(id=case_info['case_id'])
                relation_record_id = SuiteCaseRelation.objects.get(suite_id=suite, case_id=case).id
                relations_to_update.append(
                    SuiteCaseRelation(
                        id=relation_record_id,
                        order=case_info['order'],
                    )
                )
            except TestCase.DoesNotExist:
                return Response({
                    'code': ErrorCode.PARAM_ERROR.code,
                    'message': f"用例 {case_info['case_id']} 不存在",
                }, status=400)
            except SuiteCaseRelation.DoesNotExist:
                return Response({
                    'code': ErrorCode.PARAM_ERROR.code,
                    'message': f"用例 {case_info['case_id']} 不在套件 {suite.name} 中",
                }, status=400)
        SuiteCaseRelation.objects.bulk_update(relations_to_update, ['order'])
        return Response({'status': 'success'})

    @action(detail=True, methods=['post'])
    def async_execute(self, request, pk=None):
        suite = self.get_object()
        suite.status = 'running'
        suite.start_time = timezone.now()
        suite.save()

        # 触发后台任务
        async_test_runner.delay(suite.id)  # 使用django-background-tasks或Celery
        return Response({'status': '任务已启动'}, status=202)


class TestExecutionViewSet(viewsets.ModelViewSet):
    queryset = TestExecution.objects.all()
    serializer_class = TestExecutionSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """触发执行套件"""
        execution = self.get_object()
        execution.status = 'running'
        execution.save()

        # 调用异步执行任务（示例伪代码）
        # execute_suite.delay(execution.id)

        return Response({'task_id': 'execution_' + str(execution.id)})

