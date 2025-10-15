from rest_framework.decorators import api_view
from rest_framework import status
import socket
import requests
import time
import threading
import datetime
from apps.ui_case.live import emit_run_event
import logging
from common.utils import APIResponse
import uuid

log = logging.getLogger('django')

# 交易相关的全局变量
active_trading_threads = {}


def is_ip_connectable(ip, port, timeout=3):
    """
    测试IP端口是否可连接
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, int(port)))
        return True
    except socket.error:
        return False
    finally:
        sock.close()


class TradingWorker:
    """
    交易执行工作线程类，模拟trading_windows.py中的WorkerThread功能
    """

    def __init__(self, thread_id, config, run_id):
        self.thread_id = thread_id
        self.config = config
        self.run_id = run_id
        self.stopped = False

    def stop(self):
        self.stopped = True

    def push_log(self, message):
        """
        通过WebSocket推送日志消息
        """
        try:
            emit_run_event(self.run_id, {
                'type': 'log',
                'message': f'[{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {message}'
            })
        except Exception as e:
            log.error(f"推送日志失败: {str(e)}")

    def run(self):
        """
        执行交易任务
        """
        try:
            if self.config['server_type'] == "MT4":
                self.run_mt4()
            else:
                self.run_mt5()
        except Exception as e:
            error_msg = f"线程 {self.thread_id} 发生错误: {str(e)}"
            self.push_log(error_msg)
            log.error(error_msg)

        finally:
            # 通知前端此线程已完成
            self.push_log(f"线程 {self.thread_id} 完成任务!")
            # 从活动线程中移除
            if self.run_id in active_trading_threads:
                if self.thread_id in active_trading_threads[self.run_id]:
                    del active_trading_threads[self.run_id][self.thread_id]
                # 如果没有活动线程了，通知前端任务完成
                if not active_trading_threads[self.run_id]:
                    del active_trading_threads[self.run_id]
                    try:
                        emit_run_event(self.run_id, {
                            'type': 'status',
                            'status': 'completed',
                            'progress': 100,
                            'message': '所有交易任务已完成'
                        })
                    except Exception as e:
                        log.error(f"推送完成状态失败: {str(e)}")

    def run_mt4(self):
        """
        执行MT4交易
        """
        open_num = self.config['open_num']
        for i in range(open_num):
            if self.stopped:
                self.push_log(f'线程 {self.thread_id} 被终止！')
                return

            request_data = {
                'login': int(self.config['ta']),
                'symbol': self.config['symbol'],
                'volume': float(self.config['volume']) * 100,
                'type': self.config['order_type_dict'][self.config['cmd']],
                'price': float(self.config['price']) if self.config['price'] else 100,
                'action': 0,
                'comment': self.config['comment']
            }
            request_head = {
                'content-type': 'application/json',
                'server_name': self.config['server_name'],
                'timestamp': str(int(time.time())),
            }

            try:
                self.push_log(f'[{self.thread_id}-{i + 1}] 准备发送开单请求...')
                r_open = requests.post(self.config['url'], json=request_data, headers=request_head, timeout=10)
                log_msg = f'[{self.thread_id}-{i + 1}] - 【开单】状态码：{r_open.status_code} | 接口返回信息：{r_open.text}'
                self.push_log(log_msg)

                if int(self.config['function']) == 2:  # 开单+关单
                    if r_open.status_code == 200:
                        try:
                            response_json = r_open.json()
                            if response_json.get('code') == 0:
                                order_id = response_json['data']['deal']

                                close_request_data = {
                                    'login': int(request_data['login']),
                                    'symbol': request_data['symbol'],
                                    'volume': request_data['volume'],
                                    'type': request_data['type'],
                                    'price': request_data['price'],
                                    'action': 1,
                                    'deal': order_id
                                }

                                r_close = requests.post(self.config['url'], json=close_request_data,
                                                        headers=request_head, timeout=10)
                                close_log = f'[{self.thread_id}-{i + 1}] - 【关单】状态码：{r_close.status_code} | 接口返回信息：{r_close.text}'
                                self.push_log(close_log)
                            else:
                                self.push_log(f'开单返回错误，无法关单: {response_json.get("message", "")}')
                        except Exception as e:
                            self.push_log(f'解析开单返回结果失败: {str(e)}')
                    else:
                        self.push_log(f'开单请求失败，无法关单')
            except Exception as e:
                self.push_log(f'请求异常: {str(e)}')

    def run_mt5(self):
        """
        执行MT5交易
        """
        open_num = self.config['open_num']
        for i in range(open_num):
            if self.stopped:
                self.push_log(f'线程 {self.thread_id} 被终止！')
                return

            request_data = {
                'login': int(self.config['ta']),
                'symbol': self.config['symbol'],
                'volume': float(self.config['volume']) * 100,
                'type': self.config['order_type_dict'][self.config['cmd']],
                'price': float(self.config['price']) if self.config['price'] else 100,
                'comment': self.config['comment']
            }
            request_head = {
                'content-type': 'application/json',
                'server_name': self.config['server_name'],
                'timestamp': str(int(time.time())),
            }

            try:
                self.push_log(f'[{self.thread_id}-{i + 1}] 准备发送开单请求...')
                r_open = requests.post(self.config['url'], json=request_data, headers=request_head, timeout=10)
                log_msg = f'[{self.thread_id}-{i + 1}] - 【开单】状态码：{r_open.status_code} | 接口返回信息：{r_open.text}'
                self.push_log(log_msg)
            except Exception as e:
                self.push_log(f'请求异常: {str(e)}')


@api_view(['POST'])
def test_connection(request):
    """
    测试链接地址是否可用的接口
    请求参数：
    {"ip": "10.12.6.18", "port": "8080"}
    """
    try:
        ip = request.data.get('ip', '').strip()
        port = request.data.get('port', '').strip()

        if not ip or not port:
            return APIResponse("IP和端口不能为空", status=status.HTTP_200_OK)

        log.info(f"测试连接: {ip}:{port}")
        if is_ip_connectable(ip, port):
            return APIResponse({"status": "success", "message": "地址访问成功"}, status=status.HTTP_200_OK)
        else:
            return APIResponse({"status": "error", "message": "地址链接失败，请检查地址是否正确或网络是否正常"},
                               status=status.HTTP_200_OK)
    except Exception as e:
        log.error(f"测试连接失败: {str(e)}")
        return APIResponse({"status": "error", "message": f"测试连接时发生错误: {str(e)}"},
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def trade_api(request):
    """
    交易接口，功能与trading_windows.py一致
    请求参数：
    {
        "ip": "10.12.6.18",
        "port": "8080",
        "server_type": "MT4",
        "function": "1",  # 1:仅开单, 2:开单+关单
        "server_name": "服务器名称",
        "ta": "交易账号",
        "cmd": "buy",  # buy或sell
        "volume": "1",  # 交易手数
        "comment": "备注",
        "price": "100",
        "open_num": 1,  # 下单次数
        "symbol": "EURUSD",
        "thread_num": 1  # 线程数量
    }
    """
    try:
        # 生成唯一的run_id
        run_id = str(uuid.uuid4())

        # 初始化配置
        ip = str(request.data.get('ip', '')).strip()
        port = str(request.data.get('port', '')).strip()
        thread_num = int(request.data.get('thread_num', 1))

        if not ip or not port:
            return APIResponse("IP和端口不能为空", status=status.HTTP_200_OK)

        # 构建配置
        order_type_dict = {'buy': 0, 'sell': 1}
        api_path = '/api/deal/add'
        config = {
            'ip': ip,
            'port': port,
            'server_type': request.data.get('server_type', 'MT4'),
            'function': request.data.get('function', '1'),
            'server_name': str(request.data.get('server_name', '')).strip(),
            'ta': str(request.data.get('ta', '')).strip(),
            'cmd': request.data.get('cmd', 'buy'),
            'volume': str(request.data.get('volume', '')).strip(),
            'comment': str(request.data.get('comment', '')).strip(),
            'price': str(request.data.get('price', '')).strip(),
            'open_num': int(request.data.get('open_num', 1)),
            'symbol': str(request.data.get('symbol', '')).strip().upper(),
            'order_type_dict': order_type_dict,
            'api_path': api_path
        }

        # 构造URL
        url = f'http://{ip}:{port}{api_path}'
        if 'http' in ip:
            url = f'{ip}:{port}{api_path}'
        config['url'] = url

        # 验证IP端口
        if not is_ip_connectable(ip, port):
            return APIResponse({"status": "error", "message": "IP端口异常，无法连接"}, status=status.HTTP_200_OK)

        # 验证必要字段
        required_fields = {
            'ta': '交易帐号',
            'symbol': '交易产品',
            'volume': '交易手数',
            'server_name': '服务器名称',
            'price': '价格',
            'comment': '备注',
        }

        for field, value in required_fields.items():
            if not config[field]:
                return APIResponse({"status": "error", "message": f'{value} 不能为空!'}, status=status.HTTP_200_OK)

        # 初始化活动线程字典
        active_trading_threads[run_id] = {}

        # 推送初始状态和交易配置信息
        try:
            emit_run_event(run_id, {
                'type': 'status',
                'status': 'running',
                'progress': 0,
                'message': '交易任务已开始'
            })

            emit_run_event(run_id, {
                'type': 'config',
                'config': {
                    'function': config['function'],
                    'server_type': config['server_type'],
                    'symbol': config['symbol'],
                    'volume': config['volume'],
                    'order_type': config['cmd'],
                    'thread_num': thread_num,
                    'open_num': config['open_num']
                }
            })
        except Exception as e:
            log.error(f"推送初始状态失败: {str(e)}")

        # 创建并启动工作线程
        for i in range(thread_num):
            worker = TradingWorker(i + 1, config, run_id)
            active_trading_threads[run_id][i + 1] = worker
            thread = threading.Thread(target=worker.run)
            thread.daemon = True
            thread.start()

        return APIResponse({
            "status": "success",
            "message": "交易任务已开始",
            "run_id": run_id,
            "websocket_url": f"ws://{request.get_host()}/api/ws/run/{run_id}/"
        }, status=status.HTTP_202_ACCEPTED)

    except Exception as e:
        log.error(f"交易接口执行失败: {str(e)}")
        return APIResponse({"status": "error", "message": f"执行交易时发生错误: {str(e)}"},
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def stop_trade(request):
    """
    停止交易任务的接口
    请求参数：{"run_id": "uuid-string"}
    """
    try:
        run_id = request.data.get('run_id', '')

        if not run_id:
            return APIResponse({"status": "error", "message": "run_id不能为空"}, status=status.HTTP_200_OK)

        if run_id in active_trading_threads:
            for worker in active_trading_threads[run_id].values():
                worker.stop()

            try:
                emit_run_event(run_id, {
                    'type': 'status',
                    'status': 'stopping',
                    'message': '已发送停止信号，等待线程结束...'
                })
            except Exception as e:
                log.error(f"推送停止状态失败: {str(e)}")

            return APIResponse({"status": "success", "message": "已发送停止信号"}, status=status.HTTP_200_OK)
        else:
            return APIResponse({"status": "error", "message": "未找到对应的交易任务"}, status=status.HTTP_200_OK)

    except Exception as e:
        log.error(f"停止交易任务失败: {str(e)}")
        return APIResponse({"status": "error", "message": f"停止交易时发生错误: {str(e)}"},
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)
