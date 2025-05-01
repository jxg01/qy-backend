from rest_framework import serializers
from users.models import UserProfile
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from common.error_codes import ErrorCode
from common.exceptions import BusinessException
import django_filters


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # 手动执行认证流程
        user = authenticate(
            request=self.context.get('request'),
            username=attrs.get(self.username_field),
            password=attrs.get('password')
        )
        # 精准错误判断
        print('before if ::: ')
        if not user:
            if not UserProfile.objects.filter(username=attrs['username']).exists():
                raise BusinessException(ErrorCode.USER_NOT_EXISTS)
            else:
                raise BusinessException(ErrorCode.PASSWORD_ERROR)

        data = super().validate(attrs)
        print('login data ??? === ', data)
        return {
            "code": 0,
            "message": "登录成功",
            "data": {
                "access": data["access"],
                "refresh": data["refresh"],
                "username": user.username
            }
        }


class UserFilter(django_filters.FilterSet):
    """ 定义字段，搜索方式：模糊搜索 """
    username = django_filters.CharFilter(field_name='username', lookup_expr='icontains')
    email = django_filters.CharFilter(field_name='email', lookup_expr='icontains')

    class Meta:
        model = UserProfile
        fields = ['username', 'email']


class UserSerializer(serializers.ModelSerializer):
    update_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    date_joined = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    password_confirm = serializers.CharField(write_only=True, required=True, help_text='确认密码')

    class Meta:
        model = UserProfile
        fields = (
            'id', 'username', 'password', 'password_confirm', 'email', 'update_time', 'date_joined'
        )

        extra_kwargs = {
            'password': {'write_only': True, 'style': {'input_type': 'password'}},
            'password_confirm': {'write_only': True, 'style': {'input_type': 'password'}},
            'email': {
                'error_messages': {
                    'invalid': '邮箱格式不正确'  # 通过 Meta 定义其他字段
                }
            },
            'username': {
                'error_messages': {
                    'required': '用户名不能为空',  # 覆盖默认空值错误
                    'blank': '用户名不能为空',
                    'max_length': '用户名长度不能超过20字符'
                },
            }
        }

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        pwd = validated_data.pop('password', None)
        instance = UserProfile.objects.create_user(**validated_data)
        if pwd is not None:
            instance.set_password(pwd)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        validated_data.pop('password_confirm')
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        pwd = validated_data.pop('password', None)
        if pwd is not None:
            instance.set_password(pwd)
        instance.save()
        return instance

    def validate_username(self, value):
        instance = self.instance
        current_username = getattr(instance, 'username', None)
        # 忽略大小写比较
        if instance and value.lower() == current_username.lower():
            return value
        # 忽略大小写
        if UserProfile.objects.filter(username__iexact=value).exists():
            raise BusinessException(ErrorCode.USERNAME_EXISTS)
        if len(value) < 4:
            raise serializers.ValidationError('username长度不能小于4！')
        return value

    def validate_email(self, value):
        instance = self.instance
        current_username = getattr(instance, 'email', None)
        # 忽略大小写比较
        if instance and value.lower() == current_username.lower():
            return value
        if UserProfile.objects.filter(email=value).exists():
            raise BusinessException(ErrorCode.EMAIL_EXISTS)
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise BusinessException(ErrorCode.PASSWORD_DIFFERENT)
        return super().validate(attrs)


class UserRegisterSerializer(serializers.ModelSerializer):
    password_confirm = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    username = serializers.CharField()

    class Meta:
        model = UserProfile
        fields = ['username', 'email', 'password', 'password_confirm']
        extra_kwargs = {
            'password': {'write_only': True,
                         'error_messages': {
                            'required': '密码不能为空',  # 覆盖默认空值错误
                            'blank': '密码不能为空',
                            }
                         },
            'username': {
                'error_messages': {
                    'required': '用户名不能为空',  # 覆盖默认空值错误
                    'blank': '用户名不能为空',
                    'max_length': '用户名长度不能超过20字符',
                },
            },
            'password_confirm': {
                'write_only': True,
                'error_messages': {
                    'required': '确认密码不能为空',  # 覆盖默认空值错误
                    'blank': '确认密码不能为空',
                },
            }
        }

    def validate_username(self, value):
        if UserProfile.objects.filter(username=value).exists():
            raise BusinessException(ErrorCode.REGISTER_USER_EXISTS)
        return value

    def validate_email(self, value):
        if UserProfile.objects.filter(email=value).exists():
            raise BusinessException(ErrorCode.REGISTER_EMAIL_EXISTS)
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise BusinessException(ErrorCode.PASSWORD_DIFFERENT)
        return super().validate(attrs)

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        pwd = validated_data.pop('password', None)
        instance = UserProfile.objects.create_user(**validated_data)
        if pwd is not None:
            instance.set_password(pwd)
        instance.save()
        return instance
