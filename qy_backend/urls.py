"""qy_backend URL Configuration

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
from ui_case import views as ui_case_views
from ScheduledTasks.views import ScheduledTaskViewSet, ScheduledTaskResultViewSet
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from mt_tool.views import test_connection, trade_api, stop_trade, MTToolConfigView

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
router.register('scheduled-task-results', ScheduledTaskResultViewSet, basename='scheduled-task-results')

router.register('home', HomeStatisticViewSet, basename='home')

router.register('python-code', PythonCodeView, basename='python-code')
# trade
router.register('mt-tool-config', MTToolConfigView, basename='mt-tool-config')

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

    # 交易相关接口
    path('api/test-connection/', test_connection, name='test_connection'),
    path('api/trade/', trade_api, name='trade_api'),
    path('api/stop-trade/', stop_trade, name='stop_trade'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
