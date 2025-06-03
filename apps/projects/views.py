from common.utils import APIResponse
from projects.models import Projects, GlobalVariable, ProjectEnvs
from projects.projectsSerialize import (ProjectsSerialize, ProjectsFilter, GlobalVariableSerialize,
                                        GlobalVariableFilter, ProjectEnvsSerialize)
from rest_framework import viewsets, permissions
from rest_framework import status
import logging

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
