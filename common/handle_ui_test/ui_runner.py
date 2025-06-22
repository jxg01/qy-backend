import asyncio
import json
import time
import traceback
from typing import List, Dict, Tuple
from playwright.async_api import async_playwright


class UIExecutor:
    def __init__(self, steps: List[Dict], headless: bool = True):
        self.steps = steps
        self.headless = headless
        self.logs = []
        self.screenshots = []
        self.status = 'success'

    async def run(self) -> Tuple[str, List[str], List[str]]:
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=self.headless)
                context = await browser.new_context()
                page = await context.new_page()

                for idx, step in enumerate(self.steps):
                    action = step.get("action")
                    target = step.get("target")
                    value = step.get("value", "")

                    log = f"Step {idx + 1}: {action} => {target or ''} {value or ''}"
                    self.logs.append(log)

                    try:
                        if action == "goto":
                            await page.goto(target)
                        elif action == "click":
                            await page.click(target)
                        elif action == "fill":
                            await page.fill(target, value)
                        elif action == "assert_text":
                            content = await page.text_content(target)
                            assert value in content, f"Expected '{value}' in '{content}'"
                        else:
                            raise ValueError(f"Unsupported action: {action}")
                    except Exception as e:
                        self.status = 'fail'
                        error_msg = f"[ERROR] {log} => {str(e)}"
                        self.logs.append(error_msg)

                        # 保存截图
                        screenshot_path = f"screenshot_step_{idx + 1}.png"
                        await page.screenshot(path=screenshot_path)
                        self.screenshots.append(screenshot_path)
                        break

                await browser.close()

        except Exception as e:
            self.status = 'fail'
            self.logs.append("Fatal Error: " + traceback.format_exc())

        return self.status, self.logs, self.screenshots

# 用法示例（适用于 Celery 任务或 Django 视图）
if __name__ == '__main__':
    steps = json.loads(open("example_steps.json").read())
    executor = UIExecutor(steps, headless=True)
    status, logs, screenshots = asyncio.run(executor.run())
    print("状态：", status)
    print("日志：", "\n".join(logs))
    print("截图：", screenshots)
