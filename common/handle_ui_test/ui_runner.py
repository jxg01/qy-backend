import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy-backend.settings')
import django

django.setup()

from projects.models import ProjectEnvs
from ui_case.models import UiElement
from playwright.async_api import async_playwright, expect
import time
import re
import json
import asyncio
import httpx
from django.conf import settings
from common.handle_test import execute_sql
from asgiref.sync import sync_to_async
import jsonpath
from typing import Dict, List, Any, Tuple
from datetime import datetime
from celery.utils.log import get_task_logger

log = get_task_logger(__name__)


class UIExecutionEngine:
    """UI测试执行引擎"""

    def __init__(self, is_headless=True, browser_type='chromium'):
        self.is_headless = is_headless
        self.browser_type = browser_type
        self.context = {}  # 变量上下文
        self.test_start_time = 0
        self.test_name = ""
        self.test_description = ""
        self.case_status = 'passed'
        self.screenshot_path = ''
        self.pre_results = []
        self.main_results = []
        self.post_results = []
        self.execution_log = ""  # 执行日志
        self.timeout = 30000  # 等待元素超时时间（毫秒）

    def _add_log(self, message: str, level: str = "INFO"):
        """添加带时间戳的日志到执行日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.execution_log += log_entry

        # 同时输出到标准日志
        if level == "INFO":
            log.info(message)
        elif level == "WARNING":
            log.warning(message)
        elif level == "ERROR":
            log.error(message)
        elif level == "DEBUG":
            log.debug(message)

    async def fill_vars(self, obj: Any, context: Dict) -> Any:
        """填充变量到字符串、字典或列表中"""
        pattern = re.compile(r"\$\{(\w+)\}")

        if isinstance(obj, str):
            return pattern.sub(lambda m: str(context.get(m.group(1), m.group(0))), obj)
        elif isinstance(obj, dict):
            return {k: await self.fill_vars(v, context) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [await self.fill_vars(i, context) for i in obj]
        return obj

    async def extract_json_value(self, resp_json: Dict, jsonpath_value: str) -> Any:
        """使用jsonpath从JSON响应中提取值"""
        value = jsonpath.jsonpath(resp_json, jsonpath_value)
        if value:
            return value[0]
        return ''

    async def retry_operation(self, func, retries=3, delay=2, *args, **kwargs):
        """重试操作函数"""
        for attempt in range(retries):
            try:
                self._add_log(f"准备开始第[{attempt + 1}]次执行操作", "INFO")
                return await func(*args, **kwargs)
            except Exception as e:
                self._add_log(f"第[{attempt + 1}]次执行操作失败，失败原因: {str(e)}", "WARNING")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    self._add_log(f"操作重试{retries}次后仍失败: {str(e)}", "ERROR")
                    raise e

    async def execute_pre_apis(self, pre_apis: List[Dict]) -> List[Dict]:
        """执行前置API请求"""
        self._add_log("开始执行前置条件", "INFO")
        results = []

        for pre_api in pre_apis:
            try:
                result = await self.call_pre_api(pre_api, self.context)
                results.append(result)
                self._add_log(f"前置API '{pre_api.get('name', '未命名')}' 执行成功", "INFO")
            except Exception as e:
                self._add_log(f"前置API '{pre_api.get('name', '未命名')}' 执行失败: {str(e)}", "ERROR")
                results.append({
                    "request": f"API: {pre_api.get('name', '未命名')}",
                    "response": f"执行失败: {str(e)}",
                    "variables": self.context
                })

        self._add_log("前置条件执行完成", "INFO")
        return results

    async def call_pre_api(self, api_cfg: Dict, context: Dict) -> Dict:
        """调用单个前置API"""
        # 填充变量到API配置
        req_cfg = await self.fill_vars(api_cfg['request'], context)
        method = req_cfg.get('method', 'GET').upper()
        url = req_cfg['url']

        headers = req_cfg.get('headers', {})
        data = req_cfg.get('body') if isinstance(req_cfg.get('body'), dict) else json.loads(req_cfg.get('body', '{}'))
        json_data = req_cfg.get('json')

        # 记录请求信息
        self._add_log(f"执行API请求: {method} {url}", "INFO")

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            try:
                # 重试请求
                resp = await self.retry_operation(
                    client.request, retries=3, delay=2,
                    method=method, url=url, headers=headers, data=data, json=json_data
                )
                resp.raise_for_status()

                # 处理响应
                api_response = resp.text
                self._add_log(
                    f"API响应: {resp.status_code} - {api_response[:100]}{'...' if len(api_response) > 100 else ''}",
                    "INFO")

                # 提取变量
                resp_json = resp.json()
                for extract in api_cfg.get('extracts', []):
                    value = await self.extract_json_value(resp_json, extract['jsonpath'])
                    context[extract['varName']] = value
                    self._add_log(
                        f"提取变量: {extract['varName']} = {str(value)[:50]}{'...' if len(str(value)) > 50 else ''}",
                        "INFO")

                return {
                    "request": f"{method} {url}",
                    "response": api_response,
                    "variables": context.copy()
                }

            except httpx.ReadTimeout as e:
                self._add_log(f"API请求超时: {str(e)}", "ERROR")
                raise
            except Exception as e:
                self._add_log(f"API请求异常: {str(e)}", "ERROR")
                raise

    async def setup_browser_context(self, playwright):
        """设置浏览器上下文"""
        self._add_log("启动浏览器", "INFO")
        browser = await getattr(playwright, self.browser_type).launch(
            headless=self.is_headless,
            args=["--start-maximized", "--window-size=1920,1080"]
        )

        browser_context = await browser.new_context(viewport={"width": 1920, "height": 1080})

        self._add_log("浏览器环境初始化完成", "INFO")
        return browser, browser_context

    async def get_element_selector(self, element_id: int) -> str:
        """Get element selector string from database"""
        try:
            element = await sync_to_async(UiElement.objects.values('locator_type', 'locator_value').get)(id=element_id)
            return f"{element['locator_type']}={element['locator_value']}"
        except UiElement.DoesNotExist:
            self._add_log(f"Element ID {element_id} not found in database", "ERROR")
            raise ValueError(f"Element ID {element_id} not found")

    async def execute_step(self, page, step: Dict, step_index: int) -> Dict:
        """执行单个测试步骤"""
        self._add_log(f"执行步骤 {step_index + 1}: {step.get('description', step.get('action', '未知操作'))}", "INFO")

        try:
            # 填充变量到步骤配置
            step_filled = await self.fill_vars(step, self.context)
            action = step_filled.get("action")

            if 'element_id' in step_filled and type(step_filled['element_id']) == int:
                selector = await self.get_element_selector(step_filled['element_id'])
            elif 'element_id' in step_filled:
                selector = step_filled['element_id']
            else:
                selector = None

            if action == "sleep":
                seconds = float(step_filled["seconds"])
                self._add_log(f"等待 {seconds} 秒", "INFO")
                await asyncio.sleep(seconds)
                return {"step": step_filled, "status": "pass", "log": f"Slept for {seconds} seconds"}

            elif action == "goto":
                self._add_log(f"导航到: {step_filled['url']}", "INFO")
                await page.goto(step_filled["url"])
                await page.wait_for_load_state("domcontentloaded")
                return {"step": step_filled, "status": "pass", "log": f"GOTO {step_filled['url']}"}

            elif action == "input":
                text = step_filled["value"]
                # selector = step_filled['selector']
                self._add_log(f"在元素 {selector} 中输入: {text}", "INFO")
                await page.wait_for_selector(selector, state='visible', timeout=self.timeout)
                await page.fill(selector, text)
                return {"step": step_filled, "status": "pass", "log": f"Input text '{text}' into element: {selector}"}

            elif action == "execute_script":
                script = step_filled["script"]
                self._add_log(f"执行脚本: {script}", "INFO")
                result_value = await page.evaluate(script)
                return {"step": step_filled, "status": "pass",
                        "log": f"Executed script: {script}, Result: {result_value}"}

            elif action == "upload":
                file_path = os.path.join(settings.MEDIA_ROOT, step_filled["filePath"])
                # selector = step_filled['selector']
                self._add_log(f"上传文件: {file_path} 到元素: {selector}", "INFO")
                await page.wait_for_selector(selector, state='visible', timeout=self.timeout)
                await page.set_input_files(selector, file_path)
                return {"step": step_filled, "status": "pass",
                        "log": f"Uploaded file '{file_path}' to element: {selector}"}

            elif action == "click":
                # selector = step_filled['selector']
                self._add_log(f"点击元素: {selector}", "INFO")
                await page.wait_for_selector(selector, state='visible', timeout=self.timeout)
                await page.click(selector)
                return {"step": step_filled, "status": "pass", "log": f"Clicked on element: {selector}"}

            elif action == "assert":
                return await self.execute_assertion(page, step_filled)

            else:
                self._add_log(f"未知操作: {action}", "WARNING")
                return {"step": step_filled, "status": "pass", "log": "Unknown action skipped"}

        except Exception as e:
            self._add_log(f"步骤 {step_index + 1} 执行失败: {str(e)}", "ERROR")

            self.case_status = 'failed'
            self.screenshot_path = f"screenshots/step_{step_index + 1}_fail_{step.get('action', 'unknown')}_{int(time.time())}.png"
            await page.screenshot(path=os.path.join(settings.MEDIA_ROOT, self.screenshot_path), timeout=60000)
            self._add_log(f"已保存失败截图: {self.screenshot_path}", "INFO")

            return {
                'step': step,
                'status': 'fail',
                'error': str(e),
                'screenshot': self.screenshot_path,
                # 'traceback': error_traceback
            }

    async def execute_assertion(self, page, step_filled: Dict) -> Dict:
        """Execute assertion using Playwright‘s expect()"""
        assert_type = step_filled["assert_type"]
        # selector = step_filled.get('selector', '')
        # Get selector if element_id is present
        if 'element_id' in step_filled and type(step_filled['element_id']) == int:
            selector = await self.get_element_selector(step_filled['element_id'])
        elif 'element_id' in step_filled:
            selector = step_filled['element_id']
        else:
            selector = None
        expect_value = step_filled.get('expect', '').strip()

        self._add_log(f"Executing assertion: {assert_type}, Selector: {selector}, Expected: {expect_value}", "INFO")

        try:
            if assert_type == "text":
                await expect(page.locator(selector)).to_have_text(expect_value, timeout=self.timeout)
                return {"step": step_filled, "status": "pass",
                        "log": f"assert type: {assert_type} | Expected text '{expect_value}' in element: {selector}"}

            elif assert_type == "visible":
                await expect(page.locator(selector)).to_be_visible(timeout=self.timeout)
                return {"step": step_filled, "status": "pass",
                        "log": f"assert type: {assert_type} | Element '{selector}' is visible"}

            elif assert_type == "url":
                await expect(page).to_have_url(expect_value, timeout=self.timeout)
                return {"step": step_filled, "status": "pass",
                        "log": f"assert type: {assert_type} | Expected URL '{expect_value}'"}

            elif assert_type == "attribute":
                attribute = step_filled["attribute"]
                await expect(page.locator(selector)).to_have_attribute(attribute, expect_value, timeout=self.timeout)
                return {"step": step_filled, "status": "pass",
                        "log": f"assert type: {assert_type} | Expected attribute '{attribute}' to have value '{expect_value}'"}

            elif assert_type == "title":
                await expect(page).to_have_title(expect_value, timeout=self.timeout)
                return {"step": step_filled, "status": "pass",
                        "log": f"assert type: {assert_type} | Expected title '{expect_value}'"}

            else:
                raise ValueError(f"Unsupported assertion type: {assert_type}")

        except Exception as e:
            self._add_log(f"Assertion failed: {str(e)}", "ERROR")

            self.case_status = 'failed'
            self.screenshot_path = f"screenshots/assert_fail_{assert_type}_{int(time.time())}.png"
            await page.screenshot(path=os.path.join(settings.MEDIA_ROOT, self.screenshot_path), timeout=60000)
            self._add_log(f"Saved assertion failure screenshot: {self.screenshot_path}", "INFO")

            return {
                "step": step_filled,
                "status": "fail",
                "error": str(e),
                "screenshot": self.screenshot_path,
            }

    async def execute_test_steps(self, page, steps: List[Dict]) -> List[Dict]:
        """执行所有测试步骤"""
        self._add_log("开始执行测试步骤", "INFO")
        results = []

        for idx, step in enumerate(steps):
            result = await self.execute_step(page, step, idx)
            results.append(result)

            # 如果步骤失败，停止执行
            if result['status'] == 'fail':
                self._add_log(f"步骤 {idx + 1} 执行失败，停止后续步骤执行", "ERROR")
                break

        self._add_log("测试步骤执行完成", "INFO")
        return results

    async def get_db_info(self, db_env_id: int) -> Dict:
        """获取数据库配置信息"""
        return await sync_to_async(
            ProjectEnvs.objects.select_related('db_config')
            .filter(id=db_env_id)
            .values(
                'db_config__name',
                'db_config__host',
                'db_config__port',
                'db_config__username',
                'db_config__password'
            ).first
        )()

    async def execute_post_steps(self, post_steps: List[Dict]) -> List[Dict]:
        """执行后置步骤（SQL或API）"""
        self._add_log("开始执行后置步骤", "INFO")
        results = []

        for step_info in post_steps:
            step_type = step_info.get('type')
            self._add_log(f"执行后置{step_type.upper()}步骤", "INFO")

            try:
                if step_type == 'sql':
                    sql = step_info.get('sql')
                    db_env_id = step_info.get('dbEnv')

                    self._add_log(f"执行SQL: {sql}", "INFO")
                    db_info = await self.get_db_info(db_env_id)

                    if not db_info:
                        raise ValueError(f"数据库环境ID {db_env_id} 不存在")

                    db_config = {
                        'name': db_info.get('db_config__name'),
                        'host': db_info.get('db_config__host'),
                        'port': db_info.get('db_config__port'),
                        'username': db_info.get('db_config__username'),
                        'password': db_info.get('db_config__password'),
                    }

                    self._add_log(f"数据库配置: {db_config['name']}@{db_config['host']}:{db_config['port']}", "INFO")
                    sql_result = execute_sql.execute_sql_dynamic(db_config, sql)

                    self._add_log(f"SQL执行结果: {str(sql_result)[:100]}{'...' if len(str(sql_result)) > 100 else ''}",
                                  "INFO")
                    results.append({'type': 'sql', 'sql': sql, 'result': sql_result})

                else:
                    self._add_log(f"不支持的后置步骤类型: {step_type}", "WARNING")
                    results.append({'type': step_type, 'error': f"不支持的步骤类型: {step_type}"})

            except Exception as e:
                self._add_log(f"后置步骤执行失败: {str(e)}", "ERROR")
                results.append({'type': step_type, 'error': str(e)})

        self._add_log("后置步骤执行完成", "INFO")
        return results

    async def run_test_case(self, case_json: Dict) -> Tuple[str, Dict, str, str]:
        """执行完整的UI测试用例"""
        self.test_start_time = time.time()

        try:
            # 1. 执行前置API
            self.pre_results = await self.execute_pre_apis(case_json.get('pre_apis', []))

            # 2. 初始化浏览器并执行测试步骤
            async with async_playwright() as p:
                browser, browser_context = await self.setup_browser_context(p)
                page = await browser_context.new_page()

                self.main_results = await self.execute_test_steps(page, case_json.get('steps', []))

                await browser.close()
                self._add_log("浏览器已关闭", "INFO")

            # 3. 执行后置步骤
            self.post_results = await self.execute_post_steps(case_json.get('post_steps', []))

            # 5. 汇总测试结果
            all_result = {
                'pre_apis_result': self.pre_results,
                'steps_result': self.main_results,
                'post_steps_result': self.post_results
            }

            test_end_time = time.time()
            duration = test_end_time - self.test_start_time
            self._add_log(f"测试用例执行完成，状态: {self.case_status}, 耗时: {duration:.2f}秒", "INFO")

            return self.case_status, all_result, self.screenshot_path, self.execution_log

        except Exception as e:
            self._add_log(f"测试用例执行异常: {str(e)}", "ERROR")
            self.case_status = 'error'

            # 返回错误结果
            error_result = {
                'pre_apis_result': self.pre_results,
                'steps_result': self.main_results,
                'post_steps_result': self.post_results,
                'error': str(e),
            }

            return self.case_status, error_result, self.screenshot_path, self.execution_log


async def run_ui_case_tool(case_json, is_headless=True, browser_type='chromium'):
    """执行UI测试用例的工具函数"""
    # 创建执行引擎实例
    engine = UIExecutionEngine(
        is_headless=is_headless,
        browser_type=browser_type
    )

    # 执行测试用例
    return await engine.run_test_case(case_json=case_json,)
