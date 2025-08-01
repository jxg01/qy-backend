"""qy-backend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from users.views import UserViewSet, UserRegistrationViewSet, CustomTokenObtainPairView, UserSuggestionViewSet
from jk_case import views
from projects.views import (ProjectsView, GlobalVariableView, ProjectsEnvsView,
                            HomeStatisticViewSet, PythonCodeView, DBConfigView)
from rest_framework.routers import DefaultRouter
from mt_tool import views as mt_views
from ui_case import views as ui_case_views
from ScheduledTasks.views import ScheduledTaskViewSet

router = DefaultRouter()
router.register('users', UserViewSet)
router.register('suggestion', UserSuggestionViewSet)
router.register('projects', ProjectsView)
router.register('register', UserRegistrationViewSet, basename='register')
router.register('variable', GlobalVariableView)
router.register('envs', ProjectsEnvsView)
router.register('db-config', DBConfigView, basename='db-config')
# about case
router.register(r'suite', views.TestSuiteViewSet)
router.register(r'SuiteExecutionResult', views.TestExecutionViewSet)
router.register(r'CaseExecutionResult', views.CaseExecutionViewSet)

router.register(r'execution-history', views.ExecutionHistoryViewSet, basename='execution-history')

router.register(r'interfaces', views.InterFaceViewSet, basename='interfacecase')
router.register(r'testcases', views.TestCaseViewSet, basename='testcase')
router.register('modules', views.ModuleViewSet, basename='module')
# ui cases
router.register('ui-elements', ui_case_views.UiElementViewSet, basename='ui-element')
router.register('ui-modules', ui_case_views.UiTestModuleViewSet, basename='ui-module')

router.register('ui-testcases', ui_case_views.UiTestCaseViewSet, basename='ui-testcase')
router.register('ui-executions', ui_case_views.UiExecutionViewSet, basename='ui-execution')
router.register('ui-test-files', ui_case_views.UiTestFileViewSet, basename='ui-test-file')
# 定时任务
router.register('scheduled-tasks', ScheduledTaskViewSet, basename='scheduled-tasks')

router.register('home', HomeStatisticViewSet, basename='home')

router.register('python-code', PythonCodeView, basename='python-code')

schema_view = get_schema_view(
    openapi.Info(
        title="接口自动化测试平台 API",
        default_version='v1',
        description="接口测试平台所有API接口的交互文档",
        terms_of_service="https://www.example.com/terms/",
        contact=openapi.Contact(email="your@email.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)


urlpatterns = [
    path('admin/', admin.site.urls),
    # path('docs/', include_docs_urls(title='倾Y系统')),
    path('api-auth/', include('rest_framework.urls')),
    # Swagger两种风格
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),  # 推荐

    path('api/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/', include(router.urls)),

    # 任务管理
    path('api/tasks/', mt_views.TaskAPIView.as_view(), name='task-manage'),
    path('api/tasks/<str:task_id>/', mt_views.TaskStatusView.as_view(), name='task-status'),

    # 任务历史
    path('api/users/<int:user_id>/tasks/', mt_views.UserTaskHistoryView.as_view(), name='user-task-history'),


    # path('tools', Tools.as_view()),

    # path('api/users/', UserViewSet.as_view({'get': 'list'}), name='select_all_user'),
    # path('api/addUser/', UserViewSet.as_view({'post': 'create'}), name='add_user'),
    # path('api/updateUser/<int:id>/', UserViewSet.as_view({'post': 'update'}), name='update_user'),
    # # 获取访问路由上的值： <类型: id>  id 为主键
    # # path('api/users/<int:id>/', UserViewSet.as_view({'get': 'retrieve'}), name='select_user'),
    # path('api/delUser/<int:id>/', UserViewSet.as_view({'get': 'destroy'}), name='delete_user'),
    # # 项目模块
    # path('api/projects/', ProjectsView.as_view({'get': 'list'}), name='select_all_project'),
    # path('api/addProject/', ProjectsView.as_view({'post': 'create'}), name='add_project'),
    # path('api/updateProject/<int:id>/', ProjectsView.as_view({'post': 'update'}), name='update_project'),
    # path('api/delProject/<int:id>/', ProjectsView.as_view({'get': 'destroy'}), name='delete_project'),
    # # 接口模块
    # path('api/jkCases/', InterFaceCaseView.as_view({'get': 'list'}), name='select_all_jkCase'),
    # path('api/addJkCase/', InterFaceCaseView.as_view({'post': 'create'}), name='add_jkCase'),
    # path('api/deleteJkCase/<int:id>/', InterFaceCaseView.as_view({'get': 'destroy'}), name='delete_jkCase'),
    # path('api/updateCase/<int:id>/', InterFaceCaseView.as_view({'post': 'update'}), name='update_jkCase'),
    # path('api/runCase/', RunCaseView.as_view(), name='run_case'),
    # # 测试结果模块
    # path('api/results/', ResultView.as_view({'get': 'list'}), name='select_test_result'),
    # path('api/delResult/<int:id>/', ResultView.as_view({'get': 'destroy'}), name='delete_test_result'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
