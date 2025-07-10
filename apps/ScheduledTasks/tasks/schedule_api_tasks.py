from celery import shared_task

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy-backend.settings')
import django
django.setup()

from common.handle_ui_test.ui_runner import run_ui_case_tool
import asyncio
from ui_case.models import UiExecution, UiTestCase  # 假设模型放在 ui app 中
import logging
import time

log = logging.getLogger('celery.task')


@shared_task
def run_all_api_test(module_list=None, case_list=None):
    with open('abc.txt', 'w') as f:
        f.write('Hello, World!')

    log.error('🚀🚀     =========================')
    log.info('👌开始 run API API API ==== ')
    time.sleep(2)
    log.info('结束，等待了2秒 ==== 🚀')
    print('dlkajsdlfk ============================= ')
