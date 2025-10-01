import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy_backend.settings')
import django
django.setup()

from projects.models import ProjectEnvs, GlobalVariable, PythonCode
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
import re

log = get_task_logger('worker')


class UIExecutionEngine:
    """UI测试执行引擎"""

    def __init__(self, is_headless=True, browser_type='chromium', storage_state_path=None):
        self.is_headless = is_headless
        self.browser_type = browser_type
        self.storage_state_path = storage_state_path  # 存储状态文件路径
        self.context = {}  # 变量上下文
        self.python_code = ''
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

    async def get_global_variables(self):
        """获取所有全局变量"""
        try:
            # 使用sync_to_async装饰一个同步函数来获取变量
            @sync_to_async
            def get_vars():
                return dict(GlobalVariable.objects.values_list('name', 'value'))

            # global_vars = await get_vars()
            self.context.update(await get_vars())
            self._add_log(f"已加载全局变量: {list(self.context.keys())}", "INFO")
        except Exception as e:
            self._add_log(f"加载全局变量失败: {str(e)}", "ERROR")
        # return global_vars

    async def get_python_functions(self):
        """获取 Python 函数代码"""
        try:
            @sync_to_async
            def get_code():
                return PythonCode.objects.first().python_code

            python_code = await get_code()
            self._add_log("已加载 Python 函数代码", "INFO")
            return python_code
        except Exception as e:
            self._add_log(f"加载 Python 函数代码失败: {str(e)}", "ERROR")
            return ""

    async def fill_vars(self, obj: Any, context: Dict) -> Any:
        """填充变量，支持函数调用和变量替换"""
        pattern = re.compile(r"\$\{__(\w+)\((.*?)\)\}|\$\{(\w+)\}")

        if isinstance(obj, str):
            original_value = obj

            def replacement(match):
                if match.group(1):  # 函数调用
                    func_name = match.group(1)
                    args = [arg.strip() for arg in match.group(2).split(',') if arg.strip()]
                    try:
                        # 执行函数
                        namespace = {}
                        exec(self.python_code, namespace)
                        func = namespace.get(func_name)
                        if not func:
                            self._add_log(f"函数 {func_name} 未找到", "ERROR")
                            return match.group(0)
                        result = str(func(*args))
                        self._add_log(f"函数替换: ${{{func_name}({','.join(args)})}} -> {result}", "INFO")
                        return result
                    except Exception as e:
                        self._add_log(f"执行函数 {func_name} 失败: {str(e)}", "ERROR")
                        return match.group(0)
                else:  # 变量替换
                    var_name = match.group(3)
                    result = str(context.get(var_name, match.group(0)))
                    if result != match.group(0):  # 只记录成功的变量替换
                        self._add_log(f"变量替换: ${{{var_name}}} -> {result}", "INFO")
                    return result

            result = pattern.sub(replacement, obj)
            if result != original_value:
                self._add_log(f"完整替换: {original_value} -> {result}", "INFO")
            return result
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
        """执行前置API/SQL"""
        self._add_log("开始执行前置条件", "INFO")
        results = []

        for pre_api in pre_apis:
            try:
                kind = (pre_api.get('type') or pre_api.get('name') or '').lower()
                if kind == 'sql':
                    sql = pre_api.get('sql') or ''
                    db_env_id = pre_api.get('dbEnv') or pre_api.get('db_env') or pre_api.get('db') or pre_api.get('dbEnvId')
                    extracts = pre_api.get('extracts')
                    assigned, sql_result = await self.execute_sql_and_extract(sql, db_env_id, extracts)
                    results.append({"request": f"SQL", "response": sql_result, "variables": self.context.copy()})
                    self._add_log("前置SQL执行成功", "INFO")
                else:
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

        # 为不同浏览器类型设置专门的启动参数
        if self.browser_type == 'chromium':
            browser_args = [
                "--height=1080",
                "--width=1920",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
            if self.is_headless:
                browser_args.append("--headless=new")
        elif self.browser_type == 'firefox':
            browser_args = [
                "--height=1080",
                "--width=1920",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        elif self.browser_type == 'webkit':
            # WebKit专用参数，解决Docker环境中的兼容性问题
            browser_args = [
                "--no-startup-window"
            ]
        else:
            browser_args = []
            self._add_log(f"未知浏览器类型: {self.browser_type}", "WARNING")

        browser = await getattr(playwright, self.browser_type).launch(
            headless=self.is_headless,
            args=browser_args
        )

        context_options = {
            "viewport": {"width": 1920, "height": 1080}
        }

        # 只有当存储状态文件存在且不为空时才使用它
        if self.storage_state_path and os.path.exists(self.storage_state_path):
            try:
                with open(self.storage_state_path, 'r', encoding='utf-8') as f:
                    storage_content = f.read().strip()
                    if storage_content:  # 检查文件内容是否为空
                        storage_data = json.loads(storage_content)
                        if storage_data.get('cookies') or storage_data.get('origins'):  # 验证存储状态的有效性
                            context_options["storage_state"] = self.storage_state_path
                            self._add_log(f"使用有效的存储状态创建浏览器上下文: {self.storage_state_path}", "INFO")
                        else:
                            self._add_log("存储状态文件格式无效，创建新的浏览器上下文", "WARNING")
                    else:
                        self._add_log("存储状态文件为空，创建新的浏览器上下文", "WARNING")
            except (json.JSONDecodeError, IOError) as e:
                self._add_log(f"读取存储状态文件失败: {str(e)}，创建新的浏览器上下文", "WARNING")
        else:
            self._add_log("创建新的浏览器上下文（无存储状态）", "INFO")

        browser_context = await browser.new_context(**context_options)
        self._add_log("浏览器环境初始化完成", "INFO")
        return browser, browser_context

    async def save_storage_state(self, browser_context, path):
        """保存浏览器状态到文件"""
        try:
            # 首先检查文件和路径状态
            if path and os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:  # 如果文件不为空
                            storage_data = json.loads(content)
                            if storage_data.get('cookies') or storage_data.get('origins'):
                                self._add_log("存储状态文件已存在且有效，跳过保存", "INFO")
                                return True
                except (json.JSONDecodeError, IOError) as e:
                    self._add_log(f"读取现有存储状态文件失败: {str(e)}", "WARNING")

            # 获取当前的存储状态
            storage_state = await browser_context.storage_state()

            # 验证存储状态是否有效
            if not (storage_state.get('cookies') or storage_state.get('origins')):
                self._add_log("当前没有有效的存储状态需要保存", "WARNING")
                return False

            # 确保目标目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True)

            # 保存状态到文件
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(storage_state, f, indent=2)

            self._add_log(f"已成功保存浏览器状态到: {path}", "INFO")
            return True

        except Exception as e:
            self._add_log(f"保存浏览器状态失败: {str(e)}", "ERROR")
            return False

    async def get_element_selector(self, element_id: int) -> str:
        """Get element selector string from database"""
        try:
            element = await sync_to_async(UiElement.objects.values('locator_type', 'locator_value').get)(id=element_id)
            return f"{element['locator_type']}={element['locator_value']}"
        except UiElement.DoesNotExist:
            self._add_log(f"Element ID {element_id} not found in database", "ERROR")
            raise ValueError(f"Element ID {element_id} not found")

    async def get_element_handle(self, page, selector: str):
        """Convert selector string to appropriate Playwright locator"""
        if selector.startswith('data-testid='):
            # Extract the test ID value
            test_id = selector.replace('data-testid=', '')
            self._add_log(f"Using data-test-ID selector: {test_id}", "INFO")
            return page.get_by_test_id(test_id)
        else:
            return page.locator(selector)

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

            # Get element handle if selector exists
            element = await self.get_element_handle(page, selector) if selector else None

            if action == "sleep":
                seconds = float(step_filled["seconds"])
                self._add_log(f"等待 {seconds} 秒", "INFO")
                await asyncio.sleep(seconds)
                return {"step": step_filled, "status": "pass", "log": f"Slept for {seconds} seconds"}

            elif action == "wait_element":
                # 显示等待
                self._add_log(f"等待元素可见: {selector}", "INFO")
                wait_time = int(step_filled.get("wait_time"))*1000  # 默认使用 self.timeout
                await element.wait_for(state='visible', timeout=wait_time)
                return {"step": step_filled, "status": "pass",
                        "log": f"Element '{selector}' is now visible"}

            elif action == "goto":
                self._add_log(f"导航到: {step_filled['url']}", "INFO")
                await page.goto(step_filled["url"])
                await page.wait_for_load_state("domcontentloaded")
                return {"step": step_filled, "status": "pass", "log": f"GOTO {step_filled['url']}"}

            elif action == "input":
                text = step_filled["value"]
                # selector = step_filled['selector']
                self._add_log(f"在元素 {selector} 中输入: {text}", "INFO")
                # await page.wait_for_selector(selector, state='visible', timeout=self.timeout)
                # await page.fill(selector, text)
                await element.wait_for(state='visible', timeout=self.timeout)
                await element.fill(text)
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
                # await page.wait_for_selector(selector, state='visible', timeout=self.timeout)
                # await page.set_input_files(selector, file_path)
                await element.wait_for(state='visible', timeout=self.timeout)
                await element.set_input_files(file_path)
                return {"step": step_filled, "status": "pass",
                        "log": f"Uploaded file '{file_path}' to element: {selector}"}

            elif action == "click":
                # selector = step_filled['selector']
                self._add_log(f"点击元素: {selector}", "INFO")
                # await page.wait_for_selector(selector, state='visible', timeout=self.timeout)
                # await page.click(selector)
                await element.wait_for(state='visible', timeout=self.timeout)
                await element.click()
                return {"step": step_filled, "status": "pass", "log": f"Clicked on element: {selector}"}

            elif action == "assert":
                return await self.execute_assertion(page, step_filled)

            elif action == "sql":
                sql = step_filled.get("sql") or ""
                db_env_id = step_filled.get("dbEnv") or step_filled.get("db_env") or step_filled.get("db") or step_filled.get("dbEnvId")
                extracts = step_filled.get("extracts")
                assigned, sql_result = await self.execute_sql_and_extract(sql, db_env_id, extracts)
                return {"step": step_filled, "status": "pass", "log": "SQL executed", "result": sql_result, "variables": assigned}

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
        """Execute assertion using Playwright's expect()"""
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
            element = await self.get_element_handle(page, selector) if selector else None

            if assert_type == "text":
                # await expect(page.locator(selector)).to_have_text(expect_value, timeout=self.timeout)
                await expect(element).to_have_text(expect_value, timeout=self.timeout)
                return {"step": step_filled, "status": "pass",
                        "log": f"assert type: {assert_type} | Expected text '{expect_value}' in element: {selector}"}

            elif assert_type == "visible":
                # await expect(page.locator(selector)).to_be_visible(timeout=self.timeout)
                await expect(element).to_be_visible(timeout=self.timeout)
                return {"step": step_filled, "status": "pass",
                        "log": f"assert type: {assert_type} | Element '{selector}' is visible"}

            elif assert_type == "exists":
                # await expect(page.locator(selector)).to_have_count(1, timeout=self.timeout)
                await expect(element).to_have_count(1, timeout=self.timeout)
                return {"step": step_filled, "status": "pass",
                        "log": f"assert type: {assert_type} | Element '{selector}' exists"}

            elif assert_type == "url":
                # await expect(page).to_have_url(expect_value, timeout=self.timeout)
                await expect(page).to_have_url(re.compile(fr".*{expect_value}"), timeout=self.timeout)

                return {"step": step_filled, "status": "pass",
                        "log": f"assert type: {assert_type} | Expected URL '{expect_value}'"}

            elif assert_type == "attribute":
                attribute = step_filled["attribute"]
                # await expect(page.locator(selector)).to_have_attribute(attribute, expect_value, timeout=self.timeout)
                # element = await self.get_element_handle(page, selector) if selector else None
                await expect(element).to_have_attribute(
                    attribute,
                    expect_value,
                    timeout=self.timeout
                )
                return {"step": step_filled, "status": "pass",
                        "log": f"assert type: {assert_type} | Expected attribute '{attribute}' to have value '{expect_value}'"}

            elif assert_type == "title":
                # await expect(page).to_have_title(expect_value, timeout=self.timeout)
                await expect(page).to_have_title(re.compile(fr".*{expect_value}"), timeout=self.timeout)
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

    async def execute_sql_and_extract(self, sql: str, db_env_id: int, extracts=None):
        """执行 SQL 并按 extracts 提取变量到 context。返回 (保存到 context 的变量映射, 原始结果)。
        extracts 支持：
          - 列表[str]: 直接按列名提取，变量名=列名；
          - 列表[dict]: {varName: 'u_id', column: 'id', row: 0}，column 可省略，默认等于 varName；row 默认 0；
          - 为空/缺省：若结果为 SELECT 且有第一行，默认把第一行的所有列放入 context。
        """
        # 变量替换
        sql = (await self.fill_vars({'sql': sql}, self.context)).get('sql', sql) if hasattr(self, 'fill_vars') else sql

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
        self._add_log(f"执行SQL: {sql}", "INFO")

        sql_result = execute_sql.execute_sql_dynamic(db_config, sql)
        # 失败场景：工具返回 {'status':'error', 'message':...}
        if isinstance(sql_result, dict) and sql_result.get('status') == 'error':
            raise RuntimeError(f"SQL执行失败: {sql_result.get('message')}")

        assigned = {}

        def _as_first_row(res):
            if isinstance(res, list) and res and isinstance(res[0], dict):
                return res[0]
            return None

        first_row = _as_first_row(sql_result)

        if not extracts:
            # 默认把第一行所有列放入 context（常见：select id,email from users limit 1）
            if first_row:
                for k, v in first_row.items():
                    self.context[k] = v
                    assigned[k] = v
                    self._add_log(f"提取变量: {k} = {str(v)[:50]}{'...' if len(str(v))>50 else ''}", "INFO")
        else:
            # 规范化 extracts 列表
            if isinstance(extracts, dict):
                # 支持 {column: varName, ...}
                norm = []
                for col, var in extracts.items():
                    norm.append({'varName': var, 'column': col})
                extracts = norm
            for ext in extracts:
                if isinstance(ext, str):
                    var_name = ext
                    col = ext
                    row_idx = 0
                elif isinstance(ext, dict):
                    var_name = ext.get('varName') or ext.get('name') or ext.get('var') or ext.get('key')
                    col = ext.get('column') or ext.get('col') or ext.get('field') or var_name
                    row_idx = int(ext.get('row', 0) or 0)
                else:
                    continue

                value = None
                if isinstance(sql_result, list) and len(sql_result) > row_idx and isinstance(sql_result[row_idx], dict):
                    row = sql_result[row_idx]
                    if col in row:
                        value = row[col]
                    elif len(row) == 1:
                        # 单列查询时，允许未指定列名
                        value = next(iter(row.values()))
                # 赋值
                if var_name:
                    self.context[var_name] = value
                    assigned[var_name] = value
                    self._add_log(f"提取变量: {var_name} = {str(value)[:50]}{'...' if len(str(value))>50 else ''}", "INFO")

        return assigned, sql_result


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
                    db_env_id = step_info.get('dbEnv') or step_info.get('db_env') or step_info.get('db') or step_info.get('dbEnvId')
                    extracts = step_info.get('extracts')
                    assigned, sql_result = await self.execute_sql_and_extract(sql, db_env_id, extracts)
                    results.append({'type': 'sql', 'sql': sql, 'result': sql_result, 'variables': assigned})

                else:
                    self._add_log(f"不支持的后置步骤类型: {step_type}", "WARNING")
                    results.append({'type': step_type, 'error': f"不支持的步骤类型: {step_type}"})

            except Exception as e:
                self._add_log(f"后置步骤执行失败: {str(e)}", "ERROR")
                results.append({'type': step_type, 'error': str(e)})

        self._add_log("后置步骤执行完成", "INFO")
        return results

    async def run_test_case(self, case_json: Dict, save_storage_state: bool = False) -> Tuple[str, Dict, str, str]:
        """执行完整的UI测试用例"""
        self.test_start_time = time.time()

        try:
            # 初始化上下文变量，包含全局变量
            # self.context = await self.get_global_variables()
            await self.get_global_variables()
            # 加载 Python 函数代码
            self.python_code = await self.get_python_functions()
            self._add_log("初始化 Python 函数代码完成", "INFO")

            self._add_log("初始化全局变量完成。", "INFO")

            # 1. 执行前置API
            self.pre_results = await self.execute_pre_apis(case_json.get('pre_apis', []))

            # 2. 初始化浏览器并执行测试步骤
            async with async_playwright() as p:
                browser, browser_context = await self.setup_browser_context(p)
                page = await browser_context.new_page()

                self.main_results = await self.execute_test_steps(page, case_json.get('steps', []))

                # 如果需要保存浏览器状态
                if save_storage_state and self.storage_state_path:
                    await self.save_storage_state(browser_context, self.storage_state_path)

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


async def run_ui_case_tool(case_json, is_headless=True, browser_type='chromium', storage_state_path=None, save_storage_state=False):
    """执行UI测试用例的工具函数"""
    # 创建执行引擎实例
    engine = UIExecutionEngine(
        is_headless=is_headless,
        browser_type=browser_type,
        storage_state_path=storage_state_path
    )

    # 执行测试用例
    return await engine.run_test_case(case_json=case_json, save_storage_state=save_storage_state)
