from celery import Celery
import os


# 设置 Django 的默认配置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy-backend.settings')
app = Celery('qy-backend')
# 从 settings.py 加载所有以 `CELERY_` 开头的配置项
app.config_from_object('django.conf:settings', namespace='CELERY')
# 自动发现所有 Django 应用中的 tasks.py
app.autodiscover_tasks()

# 启动命令，根目录执行：
# celery -A qy-backend worker --loglevel=info

