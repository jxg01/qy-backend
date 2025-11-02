# mt_tool/views.py
from rest_framework.decorators import api_view
from rest_framework import status
import socket
import uuid
from django.utils import timezone
from common.utils import APIResponse
from mt_tool.models import MTToolConfig
from mt_tool.serializers import MTToolConfigSerializer
from rest_framework import viewsets, permissions
from mt_tool.tasks import execute_trading_with_multithreading
from ui_case.live import emit_run_event
import logging

log = logging.getLogger('django')


class MTToolConfigView(viewsets.ModelViewSet):
    queryset = MTToolConfig.objects.all()
    serializer_class = MTToolConfigSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """只返回当前登录用户的数据"""
        return MTToolConfig.objects.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )

    def perform_update(self, serializer):
        serializer.save(
            updated_by=self.request.user
        )


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
    交易接口 - 使用 Celery 任务
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
            'api_path': api_path,
            'holder_time': int(request.data.get('holder_time', 0)),
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
            log.info(f"初始状态推送成功，run_id: {run_id}")
        except Exception as e:
            log.error(f"推送初始状态失败: {str(e)}")

        # 启动单个 Celery 任务，内部使用多线程
        task = execute_trading_with_multithreading.delay(config, run_id, thread_num)
        task_id = task.id
        log.info(f"已提交多线程交易任务，线程数: {thread_num}, 任务ID: {task_id}")

        # 收到
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

        return APIResponse({
            "status": "success",
            "message": "交易任务已开始",
            "run_id": run_id,
            "task_count": thread_num,
            "websocket_url": f"{request.get_host()}/api/ws/run/{run_id}/"
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

        # 发送停止状态
        try:
            emit_run_event(run_id, {
                'type': 'status',
                'status': 'stopping',
                'message': '已发送停止信号...'
            })

            # 发送完成状态
            emit_run_event(run_id, {
                'type': 'done',
                'message': '交易任务已停止，连接即将关闭'
            })

            log.info(f"已停止交易任务，run_id: {run_id}")

        except Exception as e:
            log.error(f"推送停止状态失败: {str(e)}")

        return APIResponse({"status": "success", "message": "已发送停止信号"}, status=status.HTTP_200_OK)

    except Exception as e:
        log.error(f"停止交易任务失败: {str(e)}")
        return APIResponse({"status": "error", "message": f"停止交易时发生错误: {str(e)}"},
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)
