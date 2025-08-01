from common.utils import APIResponse
from projects.models import Projects, GlobalVariable, ProjectEnvs, PythonCode, DBConfig
from jk_case.models import (
    Projects, Module, InterFace,
    TestCase, TestSuite, TestExecution,
    CaseExecution
)
from projects.projectsSerialize import (ProjectsSerialize, ProjectsFilter, GlobalVariableSerialize,
                                        GlobalVariableFilter, ProjectEnvsSerialize, PythonCodeSerialize, DBConfigSerialize)
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
import logging
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
import re



logger = logging.Logger('projects')


class ProjectsView(viewsets.ModelViewSet):
    queryset = Projects.objects.all()
    serializer_class = ProjectsSerialize
    permission_classes = [permissions.IsAuthenticated]
    # 默认搜索
    filterset_fields = ['name']
    # 自定义模糊搜索 字段
    filterset_class = ProjectsFilter

    # def get_queryset(self):
    #     """过滤当前用户参与的项目（可根据需要扩展）"""
    #     return super().get_queryset().filter(creator=self.request.user)

    def perform_create(self, serializer):
        """自动设置创建人"""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        # 记录修改日志
        old_name = self.get_object().name
        instance = serializer.save()
        print(f"用户 {self.request.user} 将项目 {old_name} 修改为 {instance.name}")
        logger.info(
            f"用户 {self.request.user} 将项目 {old_name} 修改为 {instance.name}"
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return APIResponse(data=serializer.data)


class GlobalVariableView(viewsets.ModelViewSet):
    queryset = GlobalVariable.objects.all().order_by('-id')
    serializer_class = GlobalVariableSerialize
    permission_classes = [permissions.IsAuthenticated]
    # 默认搜索
    filterset_fields = ['name']
    # 自定义模糊搜索 字段
    filterset_class = GlobalVariableFilter

    # def get_queryset(self):
    #     """过滤当前用户参与的项目（可根据需要扩展）"""
    #     return super().get_queryset().filter(creator=self.request.user)

    def perform_create(self, serializer):
        """自动设置创建人"""
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        # 记录修改日志
        instance = serializer.save(updated_by=self.request.user)
        old_name = self.get_object().name
        print(f"用户 {self.request.user} 将全局变量 {old_name} 修改为 {instance.name}")
        logger.info(
            f"用户 {self.request.user} 将全局变量 {old_name} 修改为 {instance.name}"
        )


class ProjectsEnvsView(viewsets.ModelViewSet):
    queryset = ProjectEnvs.objects.all().order_by('-id')
    serializer_class = ProjectEnvsSerialize
    permission_classes = [permissions.IsAuthenticated]
    # # 默认搜索
    # filterset_fields = ['name']
    # # 自定义模糊搜索 字段
    # filterset_class = ProjectsFilter

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
        # 初始化查询集
        queryset = ProjectEnvs.objects.all().order_by('-id')

        # 动态构建过滤条件
        if project_id:
            queryset = queryset.filter(project=project_id)

        # page = self.paginate_queryset(queryset)
        # if page is not None:
        #     serializer = self.get_serializer(page, many=True)
        #     return self.get_paginated_response(serializer.data)

        serializer = self.serializer_class(queryset, many=True)
        return APIResponse(data=serializer.data)


class HomeStatisticViewSet(viewsets.ModelViewSet):
    """首页统计视图集"""
    # 禁用所有标准操作（list/create/retrieve/update/destroy）
    queryset = Projects.objects.none
    http_method_names = ['get']
    permission_classes = [permissions.IsAuthenticated]  # 允许匿名访问

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """首页核心统计指标"""
        # 基本统计
        data = {
            "projects": Projects.objects.count(),
            "modules": Module.objects.count(),
            "interfaces": InterFace.objects.count(),
            "testcases": TestCase.objects.count(),
            "testsuites": TestSuite.objects.count(),
            "executions": TestExecution.objects.count(),
        }

        # 今日新增
        today = timezone.now().date()
        data.update({
            "today_projects": Projects.objects.filter(created_at__date=today).count(),
            "today_testcases": TestCase.objects.filter(created_at__date=today).count(),
            "today_executions": TestExecution.objects.filter(started_at__date=today).count(),
        })

        # 最近7天执行趋势
        seven_days_ago = timezone.now() - timedelta(days=7)
        executions_by_day = TestExecution.objects.filter(
            started_at__gte=seven_days_ago
        ).extra({
            'date': "date(started_at)"
        }).values('date').annotate(
            total=Count('id'),
            passed=Count('id', filter=Q(status='passed')),
            failed=Count('id', filter=Q(status='failed'))
        ).order_by('date')

        data['execution_trend'] = list(executions_by_day)

        return APIResponse(data)

    @action(detail=False, methods=['get'])
    def recent_activities(self, request):
        """首页最近活动"""
        # 最近10条执行记录
        recent_executions = TestExecution.objects.select_related(
            'suite', 'executed_by'
        ).order_by('-started_at')[:10]

        # 最近10条用例执行
        recent_case_executions = CaseExecution.objects.select_related(
            'case', 'executed_by'
        ).order_by('-created_at')[:10]

        data = {
            "suite_executions": [
                {
                    "id": e.id,
                    "suite": e.suite.name,
                    "status": e.status,
                    "started_at": e.started_at,
                    "duration": e.duration,
                    "executed_by": e.executed_by.username if e.executed_by else None
                }
                for e in recent_executions
            ],
            "case_executions": [
                {
                    "id": ce.id,
                    "case": ce.case.name,
                    "status": ce.status,
                    "duration": ce.duration,
                    "executed_at": ce.created_at,
                    "executed_by": ce.executed_by.username if ce.executed_by else None
                }
                for ce in recent_case_executions
            ]
        }

        return APIResponse(data)

    @action(detail=False, methods=['get'])
    def status_distribution(self, request):
        """状态分布统计"""
        # 套件执行状态分布
        suite_status = TestExecution.objects.values('status').annotate(
            count=Count('id')
        )

        # 用例执行状态分布
        case_status = CaseExecution.objects.values('status').annotate(
            count=Count('id')
        )

        # 用例启用状态
        case_enabled = TestCase.objects.values('enabled').annotate(
            count=Count('id')
        )

        return APIResponse({
            "suite_status": list(suite_status),
            "case_status": list(case_status),
            "case_enabled": list(case_enabled)
        })

    @action(detail=False, methods=['get'])
    def execution_trend(self, request):
        """获取近7天执行趋势数据"""
        # 计算日期范围
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=6)  # 包括今天共7天

        # 获取套件执行趋势
        suite_trend = (
            TestExecution.objects
            .filter(started_at__date__range=[start_date, end_date])
            .annotate(date=TruncDate('started_at'))
            .values('date')
            .annotate(
                total=Count('id'),
                passed=Count('id', filter=Q(status='passed')),
                failed=Count('id', filter=Q(status='failed'))
            )
            .order_by('date')
        )

        # 获取用例执行趋势
        case_trend = (
            CaseExecution.objects
            .filter(created_at__date__range=[start_date, end_date])
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(
                total=Count('id', filter=Q(execution__isnull=True)),
                passed=Count('id', filter=Q(status='passed', execution__isnull=True)),
                failed=Count('id', filter=Q(status='failed', execution__isnull=True))
            )
            .order_by('date')
        )

        # 填充缺失的日期（确保7天都有数据）
        dates = [start_date + timedelta(days=i) for i in range(7)]

        # 格式化套件执行趋势
        suite_data = []
        for date in dates:
            entry = next((item for item in suite_trend if item['date'] == date), None)
            suite_data.append({
                "date": date,
                "total": entry["total"] if entry else 0,
                "passed": entry["passed"] if entry else 0,
                "failed": entry["failed"] if entry else 0
            })

        # 格式化用例执行趋势
        case_data = []
        for date in dates:
            entry = next((item for item in case_trend if item['date'] == date), None)
            case_data.append({
                "date": date,
                "total": entry["total"] if entry else 0,
                "passed": entry["passed"] if entry else 0,
                "failed": entry["failed"] if entry else 0
            })

        return APIResponse({
            "suite_executions": suite_data,
            "case_executions": case_data
        })


class PythonCodeView(viewsets.ModelViewSet):
    queryset = PythonCode.objects.all().order_by('-id')
    serializer_class = PythonCodeSerialize
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """自动设置创建人"""
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        # 记录修改日志
        instance = serializer.save(updated_by=self.request.user)
        old_name = self.get_object().name
        print(f"用户 {self.request.user} 将代码 {old_name} 修改为 {instance.name}")
        logger.info(
            f"用户 {self.request.user} 将代码 {old_name} 修改为 {instance.name}"
        )

    @action(detail=False, methods=['get'], url_path='function-list')
    def get_function_list(self, request):
        """获取所有Python代码中的函数列表"""
        code_str = PythonCode.objects.all().first().python_code
        pattern = r'def\s+(\w+)\s*\('
        python_function_name_list = re.findall(pattern, code_str)
        return APIResponse(data=python_function_name_list)


class DBConfigView(viewsets.ModelViewSet):
    queryset = DBConfig.objects.all().order_by('-id')
    serializer_class = DBConfigSerialize
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """自动设置创建人"""
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        # 记录修改日志
        instance = serializer.save(updated_by=self.request.user)
        old_name = self.get_object().name
        logger.info(
            f"用户 {self.request.user} 将数据库配置 {old_name} 修改为 {instance.name}"
        )
