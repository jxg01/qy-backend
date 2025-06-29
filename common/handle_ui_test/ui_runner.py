from playwright.async_api import async_playwright
import time
import re
import json
import logging
import asyncio
import httpx
from django.conf import settings
import os

log = logging.getLogger('django')


async def run_ui_case_tool(case_json, is_headless=False, browser_type='chromium'):
    log.info('start run_ui_case_tool !!!')

    async def fill_vars(obj, con):
        if isinstance(obj, str):
            return re.sub(r"\$\{(\w+)\}", lambda m: str(con.get(m.group(1), m.group(0))), obj)
        elif isinstance(obj, dict):
            return {k: await fill_vars(v, con) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [await fill_vars(i, con) for i in obj]
        else:
            return obj

    async def extract_json_value(resp_json, jsonpath):
        key = jsonpath.lstrip("$.")
        return resp_json.get(key)

    async def call_pre_api(api_cfg, cont):
        req_cfg = await fill_vars(api_cfg['request'], cont)
        method = req_cfg.get('method', 'GET').upper()
        if api_cfg.get('name') == 'token':
            url = req_cfg['url']
            if 'http' in url:
                cont['domain'] = url.split('/')[2]
            else:
                cont['domain'] = url.split('/')[0]

        headers = req_cfg.get('headers', {})
        data = req_cfg.get('body') if isinstance(req_cfg.get('body'), dict) else json.loads(req_cfg.get('body'))
        json_data = req_cfg.get('json')
        async with httpx.AsyncClient() as client:
            resp = await client.request(method, url, headers=headers, data=data, json=json_data)
            log.info(f'登录接口返回结果(未处理)：{resp.text}')
            resp.raise_for_status()
            resp_json = resp.json()
            for extract in api_cfg.get('extracts', []):
                value = await extract_json_value(resp_json, extract['jsonpath'])
                cont[extract['varName']] = value

    context = {}

    # 1. Pre-API (e.g., token retrieval)
    log.info('开始执行前置条件.......')
    for pre_api in case_json.get('pre_apis', []):
        await call_pre_api(pre_api, context)
        log.info(f"Token retrieved: {context.get('token', 'Not set')}")

    log.info('开始启动浏览器.......')
    async with async_playwright() as p:
        browser = await getattr(p, browser_type).launch(headless=is_headless)
        browser_context = await browser.new_context()

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
                'value': context.get("token", ""),
                'domain': context.get("domain", ""),
                'path': '/'
            }
            await browser_context.add_cookies([cookie])

        page = await browser_context.new_page()

        main_results = []
        case_status = 'success'
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
                    # file_base_root =
                    # file_path = file_base_root + step_filled["filePath"]
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
                        elif assert_type == "visible":
                            await page.wait_for_selector(step_filled['selector'], state='visible')
                            is_visible = await page.is_visible(step_filled["selector"])
                            assert is_visible, f"Element '{step_filled['selector']}' is not visible"
                        elif assert_type == "url":
                            current_url = page.url
                            assert step_filled[
                                       "expect"] in current_url, f"Expected '{step_filled['expect']}' in URL '{current_url}'"
                        elif assert_type == "attribute":
                            await page.wait_for_selector(step_filled['selector'], state='visible')
                            attr_value = await page.get_attribute(step_filled["selector"], step_filled["attribute"])
                            assert step_filled[
                                       "expect"] in attr_value, f"Expected '{step_filled['expect']}' in attribute '{attr_value}'"
                        elif assert_type == "title":
                            current_title = await page.title()
                            assert step_filled[
                                       "expect"] in current_title, f"Expected '{step_filled['expect']}' in title '{current_title}'"

                        result = {"step": step_filled, "status": "pass", "log": "Assertion passed"}
                    except AssertionError as e:
                        case_status = 'fail'
                        screenshot_path = f"screenshots/step_{idx + 1}_fail_assert.png"
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
                case_status = 'fail'
                screenshot_path = f"screenshots/step_{idx + 1}_fail_{step['action']}.png"
                await page.screenshot(path=os.path.join(settings.MEDIA_ROOT, screenshot_path))
                result = {
                    'step': step, 'status': 'fail', 'error': str(e), 'screenshot': screenshot_path
                }
                main_results.append(result)
                break  # Stop on failure
            main_results.append(result)
        await browser.close()
    # 执行后置sql ｜ api
    for i in case_json.get('post_', []):
        print(i)
    log.info('end execute ui test case !!!')
    # return {"steps": main_results, "context": context, "screenshot_path": screenshot_path}
    return case_status, main_results, screenshot_path


# 拉取任务 & 回调平台的接口建议见下文
if __name__ == '__main__':
    # 示例用法
    case_json1 = {
        "env": {
            "browser": "chromium",
            "headless": True
        },
        "pre_apis": [
            {
                "name": "token",
                "request": {
                    "method": "POST",
                    "url": "https://portal-tmgm-uat.lifebytecrm.dev/api/authorizations/member",
                    "body": "{\"username\": \"eddy.jiang@lifebyte.io\", \"password\": \"Lb%.6688\"}",
                },
                "extracts": [
                    {"varName": "token", "jsonpath": "$.access_token"}
                ]
            }
        ],
        "steps": [
            # {"action": "set_header", "header": {"authorization": "Bearer ${token}", "Accept": "application/prs.CRM-Back-End.v2+json"}},

            {"action": "goto", "url": "https://portal-tmgm-uat.lifebytecrm.dev/dashboard"},
            # {"action": "sleep", "seconds": '5'},
            {"action": "click", "selector": "xpath=//span[text()='Promotions']"},
            # {"action": "sleep", "seconds": '5'},
            {"action": "click", "selector": "xpath=//span[text()='首頁']"},
            # {"action": "sleep", "seconds": '5'},
            # {"action": "click", "element": {"locator_type": "xpath", "locator_value": '//span[text()="首頁"]'}},
            # {"action": "sleep", "seconds": '15'},
            # {"action": "click", "element": {"locator_type": "xpath", "locator_value": '//div[@data-testid="country"]'}},
            # {"action": "sleep", "seconds": '1'},
            # {"action": "click", "element": {"locator_type": "xpath", "locator_value": "//div[@class='el-select-dropdown']//li/span[text()='Laos']"}},
            # {"action": "sleep", "seconds": '1'},
            # {"action": "input", "element": {"locator_type": "xpath", "locator_value": '//input[@placeholder="Last Name"]'}, "text": "xxxccc"},
            # {"action": "sleep", "seconds": '1'},
            # {"action": "input", "element": {"locator_type": "id", "locator_value": "password"}, "text": "password123"},
            # {"action": "click", "element": {"locator_type": "css", "locator_value": ".login-button"}},
            {"action": "assert", "assert_type": "title", "expect": "TMGM-1"}
        ]
    }
    # r = run_case_new(case_json)
    results = asyncio.run(run_ui_case_tool(case_json1))
    print("Execution Result:", results)
    # print('================================ \n', r)

"""
{
    "url": "https://portal-tmgm-cn-2-qa.lbcrmsit.com/api/authorizations/member",
    "method": "POST",
    "body": '{"username": "eddy.jiang1@lifebyte.io", "password": "Lb%.6688"}',
    "extracts": [
        {
            "varName": "token",
            "jsonpath": "$.access_token"
        }
    ]
}
"""
