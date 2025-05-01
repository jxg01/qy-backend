from django.db import models
from django.contrib.auth.models import AbstractUser


class UserProfile(AbstractUser):
    class Meta:
        db_table = 'qy_user'
    #     verbose_name_plural = verbose_name = '用户'
    #
    # nick_name = models.CharField(max_length=30, null=True, verbose_name='昵称', help_text='昵称')
    # mobile = models.CharField(max_length=11, verbose_name='电话', help_text='电话')
    update_time = models.DateTimeField(null=True, auto_now=True)
    # last_login = models.DateTimeField(null=True)
    #
    # def __str__(self):
    #     if self.nick_name:
    #         return self.nick_name
    #     else:
    #         return self.username
