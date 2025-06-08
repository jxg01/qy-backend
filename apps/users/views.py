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
