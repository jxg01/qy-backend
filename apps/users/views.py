from users.models import UserProfile, UserSuggestion
from users.userSerialize import UserSerializer, CustomTokenObtainPairSerializer, UserRegisterSerializer, UserFilter, UserSuggestionSerialize
from rest_framework import viewsets, permissions, mixins
from common.utils import APIResponse
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import status
from common.error_codes import ErrorCode
import logging
from common.exceptions import BusinessException
# from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone


logger = logging.Logger('users')


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all().order_by('-id')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]  # 仅管理员可操作
    # 默认搜索
    filterset_fields = ['username', 'email']
    # 自定义模糊搜索 字段
    filterset_class = UserFilter

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance == request.user:
            raise BusinessException(ErrorCode.DELETE_CURRENT_USER)
        self.perform_destroy(instance)
        return APIResponse(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        """
        修改密码
        {
            "old_password": "123456",
            "new_password": "112233"
        }
        """
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        # 验证参数
        if not old_password or not new_password:
            raise BusinessException(ErrorCode.INVALID_PARAMS)

        # 验证旧密码
        if not user.check_password(old_password):
            raise BusinessException(ErrorCode.OLD_PASSWORD_ERROR)

        # 验证新密码不能和旧密码相同
        if old_password == new_password:
            raise BusinessException(ErrorCode.PASSWORD_SAME)

        # 设置新密码
        user.password = make_password(new_password)
        user.password_changed_at = timezone.now()
        user.save()

        # 使所有已存在的token失效
        RefreshToken.for_user(user)

        return APIResponse(data="密码修改成功")


class UserRegistrationViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        res_data = {
            'code': 0,
            'message': '注册成功',
            'data': serializer.data
        }
        return Response(data=res_data, status=status.HTTP_200_OK)


class UserSuggestionViewSet(viewsets.GenericViewSet,
                            mixins.CreateModelMixin,
                            mixins.DestroyModelMixin,
                            mixins.ListModelMixin):
    queryset = UserSuggestion.objects.all().order_by('-id')
    serializer_class = UserSuggestionSerialize

    def perform_create(self, serializer):
        """自动设置创建人"""
        serializer.save(created_by=self.request.user)
