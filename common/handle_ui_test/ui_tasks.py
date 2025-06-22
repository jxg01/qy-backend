from celery import shared_task
from common.handle_ui_test.ui_runner import UIExecutor
import asyncio
from ui_case.models import UiExecution, UiTestCase  # 假设模型放在 ui app 中


@shared_task
def run_ui_test_case(execution_id: int):
    try:
        execution = UiExecution.objects.get(id=execution_id)
        testcase = execution.testcase

        steps = testcase.steps  # JSONField
        executor = UIExecutor(steps, headless=True)

        status, logs, screenshots = asyncio.run(executor.run())

        execution.status = status
        execution.logs = "\n".join(logs)
        execution.screenshots = screenshots
        execution.save()

        return {"status": status, "screenshots": screenshots}

    except Exception as e:
        return {"status": "fail", "error": str(e)}
