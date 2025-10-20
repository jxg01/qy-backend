from django.db import models
from users.models import UserProfile


class MTToolConfig(models.Model):
    class Meta:
        db_table = 'mt_tool_config'
        verbose_name_plural = verbose_name = '机器翻译工具配置'

    name = models.CharField(max_length=100, verbose_name='配置名称', help_text='配置名称')
    trade_data = models.JSONField(verbose_name='历史交易配置信息', help_text='历史交易配置信息', default={})
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="创建人",
        related_name='created_mt_tool_configs'
    )
    updated_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="更新人",
        related_name='updated_mt_tool_configs'
    )

    def __str__(self):
        return self.name
