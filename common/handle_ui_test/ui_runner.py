import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy-backend.settings')
import django
django.setup()

from projects.models import ProjectEnvs
from playwright.async_api import async_playwright
import time
import re
import json
import logging
import asyncio
import httpx
from django.conf import settings
from common.handle_test import execute_sql
from asgiref.sync import sync_to_async
import jsonpath

log = logging.getLogger('celery.task')


async def run_ui_case_tool(case_json, is_headless, browser_type):
    log.info('start run_ui_case_tool !!!')

    async def fill_vars(obj, con):
        pattern = re.compile(r"\$\{(\w+)\}")
        if isinstance(obj, str):
            return pattern.sub(lambda m: str(con.get(m.group(1), m.group(0))), obj)
        elif isinstance(obj, dict):
            return {k: await fill_vars(v, con) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [await fill_vars(i, con) for i in obj]
        return obj

    async def extract_json_value(resp_json, jsonpath_value):
        value = jsonpath.jsonpath(resp_json, jsonpath_value)
        if value:
            return value[0]
        return ''

    async def retry(func, retries=3, delay=2, *args, **kwargs):
        for attempt in range(retries):
            try:
                log.info(f'🚀 准备开始第[{attempt + 1}]次执行前置接口')
                return await func(*args, **kwargs)
            except Exception as er:
                log.info(f'🚀 第[{attempt + 1}]次执行前置接口失败，失败原因是：{str(er)}')
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    raise er

    async def call_pre_api(api_cfg, cont):
        req_cfg = await fill_vars(api_cfg['request'], cont)
        method = req_cfg.get('method', 'GET').upper()
        _url = req_cfg['url']
        if api_cfg.get('name') == 'token':
            if 'http' in _url:
                cont['domain'] = _url.split('/')[2]
            else:
                cont['domain'] = _url.split('/')[0]
        headers = req_cfg.get('headers', {})
        data = req_cfg.get('body') if isinstance(req_cfg.get('body'), dict) else json.loads(req_cfg.get('body'))
        json_data = req_cfg.get('json')
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            request_info = f"header = {headers} | method = {method} | url = {_url} | formData = {data} | jsonData = {json_data}"
            api_response = ''
            log.info(request_info)
            try:
                resp = await retry(client.request, retries=3, delay=2, method=method, url=_url, headers=headers,
                                   data=data)
                resp.raise_for_status()
                log.info(f'登录接口返回结果(未处理)：{resp.text[:100]}')
                api_response = resp.text


                resp_json = resp.json()
                log.info(f"api_cfg.get('extracts', []), {api_cfg.get('extracts', [])}")
                for extract in api_cfg.get('extracts', []):
                    value = await extract_json_value(resp_json, extract['jsonpath'])
                    cont[extract['varName']] = value
            except httpx.ReadTimeout as et:
                log.error(f"请求接口超时: {str(et)}")
            except Exception as ep:
                log.error(f"请求接口特殊异常: {str(ep)}")  # Log the exception message
                log.error(f"Exception type: {type(ep).__name__}")  # Log the exception type
        return {"request": request_info, "response": api_response, "variables": cont}

    context = {}
    pre_result = []
    # 1. Pre-API (e.g., token retrieval)
    log.info('开始执行前置条件.......')
    for pre_api in case_json.get('pre_apis', []):
        result = await call_pre_api(pre_api, context)
        pre_result.append(result)
        log.info(f"内存的token为: {context.get('token', 'Not set')[:100]}")

    log.info('开始启动浏览器.......')
    async with async_playwright() as p:
        browser = await getattr(p, browser_type).launch(headless=is_headless,
                                                        args=["--start-maximized", "--window-size=1920,1080"])
        browser_context = await browser.new_context(viewport={"width": 1920, "height": 1080})

        # Inject token if required
        if any(api.get('name') == 'token' for api in case_json.get('pre_apis', [])):
            member_token = {
                "access_token": context.get("token", ""),
                "countDownModalShowExpire": int(time.time() * 1000) + 540000,
                "expire": int(time.time() * 1000) + 540000,
                "needShowExpireModal": "true",
                "session_duration": 540000
            }
            await browser_context.add_init_script(
                f"""window.localStorage.setItem("member_token", '{json.dumps(member_token)}');"""
            )

            cookie = {
                'name': 'admin_token',
                'value': str(context.get("token", "")),
                'domain': context.get("domain", ""),
                'path': '/'
            }
            await browser_context.add_cookies([cookie])

        page = await browser_context.new_page()

        main_results = []

        case_status = 'passed'
        screenshot_path = ''
        for idx, step in enumerate(case_json.get('steps', [])):
            try:
                step_filled = await fill_vars(step, context)
                result = None
                if step_filled.get("action") == "sleep":
                    seconds = float(step_filled["seconds"])
                    await asyncio.sleep(seconds)
                    result = {"step": step_filled, "status": "pass", "log": f"Slept for {seconds} seconds"}
                elif step_filled.get("action") == "goto":
                    await page.goto(step_filled["url"])
                    await page.wait_for_load_state("networkidle")
                    result = {"step": step_filled, "status": "pass", "log": f"GOTO {step_filled['url']}"}
                elif step_filled.get("action") == "input":
                    text = step_filled["value"]
                    # Ensure element is visible
                    await page.wait_for_selector(step_filled['selector'], state='visible')
                    await page.fill(step_filled['selector'], text)
                    result = {"step": step_filled, "status": "pass",
                              "log": f"Input text '{text}' into element: {step_filled['selector']}"}
                elif step_filled.get("action") == "execute_script":
                    script = step_filled["script"]
                    result_value = await page.evaluate(script)
                    result = {"step": step_filled, "status": "pass",
                              "log": f"Executed script: {script}, Result: {result_value}"}
                elif step_filled.get("action") == "upload":
                    file_path = os.path.join(settings.MEDIA_ROOT, step_filled["filePath"])
                    log.info(f'上传图片路径 === {file_path}')
                    await page.wait_for_selector(step_filled['selector'], state='visible')
                    await page.set_input_files(step_filled['selector'], file_path)
                    log.info('结束图片上传')
                    result = {"step": step_filled, "status": "pass",
                              "log": f"Uploaded file '{file_path}' to element: {step_filled['selector']}"}
                elif step_filled.get("action") == "click":
                    await page.wait_for_selector(step_filled['selector'], state='visible')
                    await page.click(step_filled['selector'])
                    result = {"step": step_filled, "status": "pass",
                              "log": f"Clicked on element: {step_filled['selector']}"}
                elif step_filled.get("action") == "assert":
                    try:
                        assert_type = step_filled["assert_type"]
                        if assert_type == "text":
                            await page.wait_for_selector(step_filled['selector'], state='visible')
                            txt = await page.text_content(step_filled["selector"])
                            assert step_filled["expect"] in txt, f"Expected '{step_filled['expect']}' in '{txt}'"
                            result = {"step": step_filled, "status": "pass",
                                      "log": f"assert type: {assert_type} | Expected '{step_filled['expect']}' in '{txt}'"}
                        elif assert_type == "visible":
                            await page.wait_for_selector(step_filled['selector'], state='visible')
                            is_visible = await page.is_visible(step_filled["selector"])
                            assert is_visible, f"Element '{step_filled['selector']}' is not visible"
                            result = {"step": step_filled, "status": "pass",
                                      "log": f"assert type: {assert_type} | Element '{step_filled['selector']}' is not visible"}
                        elif assert_type == "url":
                            current_url = page.url
                            assert step_filled[
                                       "expect"] in current_url, f"Expected '{step_filled['expect']}' in URL '{current_url}'"
                            result = {"step": step_filled, "status": "pass",
                                      "log": f"assert type: {assert_type} | Expected '{step_filled['expect']}' in URL '{current_url}'"}
                        elif assert_type == "attribute":
                            await page.wait_for_selector(step_filled['selector'], state='visible')
                            attr_value = await page.get_attribute(step_filled["selector"], step_filled["attribute"])
                            assert step_filled[
                                       "expect"] in attr_value, f"Expected '{step_filled['expect']}' in attribute '{attr_value}'"
                            result = {"step": step_filled, "status": "pass",
                                      "log": f"assert type: {assert_type} | Expected '{step_filled['expect']}' in attribute '{attr_value}'"}
                        elif assert_type == "title":
                            current_title = await page.title()
                            assert step_filled[
                                       "expect"] in current_title, f"Expected '{step_filled['expect']}' in title '{current_title}'"
                            result = {"step": step_filled, "status": "pass",
                                      "log": f"assert type: {assert_type} | Expected '{step_filled['expect']}' in title '{current_title}'"}
                        # result = {"step": step_filled, "status": "pass", "log": "Assertion passed"}
                    except AssertionError as e:
                        case_status = 'failed'
                        screenshot_path = f"screenshots/step_{idx + 1}_fail_assert_{int(time.time())}.png"
                        await page.screenshot(path=os.path.join(settings.MEDIA_ROOT, screenshot_path))
                        result = {
                            "step": step_filled,
                            "status": "fail",
                            "error": str(e),
                            "screenshot": screenshot_path
                        }
                else:
                    result = {"step": step_filled, "status": "pass", "log": "Unknown action skipped"}
            except Exception as e:
                case_status = 'failed'
                screenshot_path = f"screenshots/step_{idx + 1}_fail_{step['action']}_{int(time.time())}.png"
                await page.screenshot(path=os.path.join(settings.MEDIA_ROOT, screenshot_path))
                result = {
                    'step': step, 'status': 'fail', 'error': str(e), 'screenshot': screenshot_path
                }
                main_results.append(result)
                break  # Stop on failure
            main_results.append(result)
        await browser.close()
    # 执行后置sql ｜ api

    async def get_db_info(db_env_id):
        return await sync_to_async(ProjectEnvs.objects.select_related('db_config').filter(id=db_env_id).values(
            'db_config__name', 'db_config__host', 'db_config__port', 'db_config__username', 'db_config__password'
        ).first)()

    post_result = []
    # log.info(f'case_json => {case_json}')
    log.info(f'用例步骤执行完毕，准执行后置sql =========== {case_json.get("post_steps", [])}')
    for sql_info in case_json.get('post_steps', []):
        log.info(f'sql info ===> {sql_info}')
        if sql_info.get('type') == 'sql':
            sql = sql_info.get('sql')
            try:
                db_info = await get_db_info(sql_info.get('dbEnv'))
                db_config = {
                    'name': db_info.get('db_config__name'),
                    'host': db_info.get('db_config__host'),
                    'port': db_info.get('db_config__port'),
                    'username': db_info.get('db_config__username'),
                    'password': db_info.get('db_config__password'),
                }
                log.info(f"Executing SQL: {sql} with DB config: {db_config}")
                sql_result = execute_sql.execute_sql_dynamic(db_config, sql)
                log.info(f"SQL execution result: {sql_result}")
                log_info = {'sql': sql, 'sql_result': sql_result}
                post_result.append(log_info)

            except Exception as e:
                log_info = {'sql': sql, 'sql_result': e}
                post_result.append(log_info)
                log.error(f"Error executing post_step: {sql_info}, Error: {str(e)}")
        else:
            log.warning(f"Unsupported post_step type: {sql_info.get('type')}")
    log.info('后置sql全部执行完毕！')
    all_result = {
        'pre_apis_result': pre_result,
        'steps_result': main_results,
        'post_steps_result': post_result
    }
    # log.info(f'收集测试日志：{all_result}')
    # return {"steps": main_results, "context": context, "screenshot_path": screenshot_path}
    log.info(f'执行用例后的状态 => {case_status}')
    return case_status, all_result, screenshot_path
