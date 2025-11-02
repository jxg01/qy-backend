# mt_tool/tasks.py
import asyncio
import time
import requests
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor
from celery import shared_task
from django.utils import timezone
from asgiref.sync import async_to_sync
from ui_case.live import emit_run_event, aemit_run_event
import logging

logger = logging.getLogger('worker')


@shared_task
def execute_trading_with_multithreading(config, run_id, thread_num):
    """
    使用多线程执行交易任务的主 Celery 任务
    单个 Celery 任务中管理多个线程，所有线程完成后触发回调
    """
    try:
        # 发送任务开始状态
        emit_run_event(run_id, {
            'type': 'status',
            'status': 'running',
            'progress': 0,
            'message': f'多线程交易任务已开始，共 {thread_num} 个线程'
        })
        
        logger.info(f"开始执行多线程交易任务，run_id: {run_id}, 线程数: {thread_num}")
        
        # 使用线程池管理多个线程
        results = []
        with ThreadPoolExecutor(max_workers=thread_num) as executor:
            # 提交所有线程任务
            future_to_thread = {executor.submit(_run_thread_task, config, run_id, thread_id): thread_id 
                               for thread_id in range(1, thread_num + 1)}
            
            # 收集所有线程的执行结果
            for future in future_to_thread:
                thread_id = future_to_thread[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"线程 {thread_id} 执行完成")
                except Exception as e:
                    logger.error(f"线程 {thread_id} 执行异常: {str(e)}")
                    # 发送错误通知
                    try:
                        emit_run_event(run_id, {
                            'type': 'error',
                            'message': f'线程 {thread_id} 执行异常: {str(e)}'
                        })
                    except Exception as notify_error:
                        logger.error(f"发送错误通知失败: {str(notify_error)}")
        
        # 所有线程执行完成，发送完成消息并关闭WebSocket连接
        logger.info(f"所有线程执行完成，run_id: {run_id}")
        
        # 发送完成状态
        emit_run_event(run_id, {
            'type': 'status',
            'status': 'completed',
            'progress': 100,
            'message': '所有交易线程执行完成'
        })
        
        # 直接通知WebSocket连接关闭
        logger.info(f"发送WebSocket关闭信号，run_id: {run_id}")
        
        # 使用channel layer直接向所有连接到该run_id的客户端发送关闭消息
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        
        # 发送关闭消息，让客户端主动关闭连接
        async_to_sync(channel_layer.group_send)(
            f"run_{run_id}",
            {
                "type": "run_event", 
                "data": {
                    'type': 'close_connection',
                    'message': '所有交易任务已完成，连接即将关闭',
                    'action': 'close'
                }
            }
        )
        
        return {
            'status': 'success',
            'message': '所有线程执行完成',
            'thread_results': results
        }
        
    except Exception as e:
        logger.error(f"多线程交易任务执行失败: {str(e)}")
        # 发送错误通知
        try:
            emit_run_event(run_id, {
                'type': 'error',
                'message': f'任务执行失败: {str(e)}'
            })
            # 即使出错也要发送关闭消息
            logger.info(f"发送WebSocket错误关闭信号，run_id: {run_id}")
            
            # 使用channel layer直接发送关闭消息
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            
            async_to_sync(channel_layer.group_send)(
                f"run_{run_id}",
                {
                    "type": "run_event", 
                    "data": {
                        'type': 'close_connection',
                        'message': '任务执行出错，连接即将关闭',
                        'action': 'close',
                        'error': str(e)
                    }
                }
            )
        except Exception as notify_error:
            logger.error(f"发送通知失败: {str(notify_error)}")
        return {'status': 'error', 'error': str(e)}


def _run_thread_task(config, run_id, thread_id):
    """
    在单独线程中运行交易任务
    """
    try:
        # 在线程中运行异步交易函数
        result = async_to_sync(_execute_trading_async)(config, run_id, thread_id)
        return {
            'thread_id': thread_id,
            'result': result
        }
    except Exception as e:
        logger.error(f"线程 {thread_id} 执行失败: {str(e)}")
        # 在线程中发送错误日志
        try:
            async_to_sync(_push_log_async)(run_id, thread_id, f'线程 {thread_id} 执行失败: {str(e)}')
        except Exception as log_error:
            logger.error(f"线程 {thread_id} 发送日志失败: {str(log_error)}")
        raise e


async def _execute_trading_async(config, run_id, thread_id):
    """
    异步执行交易任务
    """
    try:
        # 推送任务开始状态
        await _push_log_async(run_id, thread_id, f'线程 {thread_id} 开始执行交易任务')

        if config['server_type'] == "MT4":
            result = await _run_mt4_trading(config, run_id, thread_id)
        else:
            result = await _run_mt5_trading(config, run_id, thread_id)

        # 推送任务完成状态
        await _push_log_async(run_id, thread_id, f'线程 {thread_id} 交易任务执行完成')

        return {'status': 'success', 'result': result}

    except Exception as e:
        error_msg = f'线程 {thread_id} 发生错误: {str(e)}'
        await _push_log_async(run_id, thread_id, error_msg)
        raise e


async def _push_log_async(run_id, thread_id, message):
    """异步推送日志"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_data = {
        'type': 'log',
        'message': f'[{timestamp}] {message}',
        'timestamp': timestamp,
        'thread_id': thread_id
    }

    # 使用 emit_run_event 的异步版本
    from ui_case.live import aemit_run_event
    await aemit_run_event(run_id, log_data)


async def _run_mt4_trading(config, run_id, thread_id):
    """执行 MT4 交易"""
    open_num = config['open_num']
    results = []

    for i in range(open_num):
        await _push_log_async(run_id, thread_id, f'[{thread_id}-{i + 1}] 准备发送开单请求...')

        request_data = {
            'login': int(config['ta']),
            'symbol': config['symbol'],
            'volume': int(float(config['volume']) * 100),
            'type': config['order_type_dict'][config['cmd']],
            'price': float(config['price']) if config['price'] else 100,
            'action': 0,
            'comment': config['comment']
        }
        request_head = {
            'content-type': 'application/json',
            'server_name': config['server_name'],
            'timestamp': str(int(time.time())),
        }

        try:
            # 使用异步方式执行 HTTP 请求
            response = await _make_http_request(
                config['url'],
                'POST',
                json=request_data,
                headers=request_head
            )

            log_msg = f'[{thread_id}-{i + 1}] - 【开单】状态码：{response.status_code} | 接口返回信息：{response.text}'
            await _push_log_async(run_id, thread_id, log_msg)

            result = {
                'thread_id': thread_id,
                'request_number': i + 1,
                'status_code': response.status_code,
                'response_text': response.text,
                'timestamp': timezone.now().isoformat()
            }
            results.append(result)

            # 处理关单逻辑
            if int(config['function']) == 2:  # 开单+关单
                if response.status_code == 200:
                    try:
                        response_json = response.json()
                        if response_json.get('code') == 0:
                            order_id = response_json['data']['deal']
                            # 异步执行延迟关单
                            asyncio.create_task(
                                _execute_delayed_close(
                                    config, run_id, thread_id, i,
                                    request_data, order_id, request_head
                                )
                            )
                            await _push_log_async(run_id, thread_id, f'[{thread_id}-{i + 1}] 已创建延迟关单任务')
                        else:
                            await _push_log_async(run_id, thread_id,
                                                  f'开单返回错误，无法关单: {response_json.get("message", "")}')
                    except Exception as e:
                        await _push_log_async(run_id, thread_id, f'解析开单返回结果失败: {str(e)}')
                else:
                    await _push_log_async(run_id, thread_id, f'开单请求失败，无法关单')

            # 添加小延迟，避免请求过于频繁
            await asyncio.sleep(0.1)

        except Exception as e:
            error_msg = f'请求异常: {str(e)}'
            await _push_log_async(run_id, thread_id, error_msg)
            results.append({
                'thread_id': thread_id,
                'request_number': i + 1,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            })

    return results


async def _run_mt5_trading(config, run_id, thread_id):
    """执行 MT5 交易"""
    open_num = config['open_num']
    results = []

    for i in range(open_num):
        await _push_log_async(run_id, thread_id, f'[{thread_id}-{i + 1}] 准备发送开单请求...')

        request_data = {
            'login': int(config['ta']),
            'symbol': config['symbol'],
            'volume': int(float(config['volume']) * 100),
            'type': config['order_type_dict'][config['cmd']],
            'price': float(config['price']) if config['price'] else 100,
            'comment': config['comment']
        }
        request_head = {
            'content-type': 'application/json',
            'server_name': config['server_name'],
            'timestamp': str(int(time.time())),
        }

        try:
            response = await _make_http_request(
                config['url'],
                'POST',
                json=request_data,
                headers=request_head
            )

            log_msg = f'[{thread_id}-{i + 1}] - 【开单】状态码：{response.status_code} | 接口返回信息：{response.text}'
            await _push_log_async(run_id, thread_id, log_msg)

            result = {
                'thread_id': thread_id,
                'request_number': i + 1,
                'status_code': response.status_code,
                'response_text': response.text,
                'timestamp': timezone.now().isoformat()
            }
            results.append(result)

        except Exception as e:
            error_msg = f'请求异常: {str(e)}'
            await _push_log_async(run_id, thread_id, error_msg)
            results.append({
                'thread_id': thread_id,
                'request_number': i + 1,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            })

    return results


async def _execute_delayed_close(config, run_id, thread_id, request_index, order_data, order_id, request_head):
    """执行延迟关单"""
    try:
        await _push_log_async(run_id, thread_id,
                              f'[{thread_id}-{request_index + 1}] - 等待 {config["holder_time"]} 秒后执行关单...')
        await asyncio.sleep(config['holder_time'])

        close_request_data = {
            'login': int(order_data['login']),
            'symbol': order_data['symbol'],
            'volume': order_data['volume'],
            'type': order_data['type'],
            'price': order_data['price'],
            'action': 1,
            'deal': order_id
        }
        request_head['timestamp'] = str(int(time.time()))

        response = await _make_http_request(
            config['url'],
            'POST',
            json=close_request_data,
            headers=request_head
        )

        close_log = f'[{thread_id}-{request_index + 1}] - 【关单】状态码：{response.status_code} | 接口返回信息：{response.text}'
        await _push_log_async(run_id, thread_id, close_log)

    except Exception as e:
        await _push_log_async(run_id, thread_id, f'关单执行失败: {str(e)}')


async def _make_http_request(url, method, **kwargs):
    """异步执行 HTTP 请求"""
    loop = asyncio.get_event_loop()

    def sync_request():
        if method.upper() == 'POST':
            return requests.post(url, **kwargs)
        elif method.upper() == 'GET':
            return requests.get(url, **kwargs)
        else:
            raise ValueError(f"不支持的HTTP方法: {method}")

    # 在线程池中执行同步请求
    response = await loop.run_in_executor(None, sync_request)
    return response
