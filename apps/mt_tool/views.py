from rest_framework.views import APIView
from rest_framework.response import Response
import requests
import threading
import time
import socket

interrupt_flag = threading.Event()


class Tools(APIView):
    def get(self, request):
        """ 中断任务 """
        interrupt_flag.set()
        return Response({'status': '任务中断了啊--------'})

    def post(self, request):
        """
        启动多线程任务

        参数：
        {"ts": 1, "tn": 4, "ps": 123}

        :param request:
        :return:
        """

        interrupt_flag.clear()

        print(request.data)
        d = request.data

        thread_num = d['ts']
        task_num = d['tn']
        print(thread_num)
        print(task_num)

        p = {"server_name": "abc", "trading_account": "123456", "key": "P1222", "symbol": "AUDUSD"}

        request_data = {
            "servername": 3,
            "size": 1,
            "private_key": 2,
            "list": [
                {
                    "login": 3,
                    "symbol": 1,
                    "comment": 2,
                    "volume": 3,
                    "cmd": 2
                }
            ]
        }
        for x in range(thread_num):
            t = threading.Thread(target=open_order, args=(p, task_num, x))
            t.start()
        return Response({'status': '任务已启动，请稍后？？？？？？？？'})


def open_order(params, n, t_id):
    """ 13 """
    request_head = {'content-type': 'application/json'}
    for i in range(n+1):
        if interrupt_flag.is_set():
            print('线程被终止啦啦啦啦啦 准备退出')
            return

        print(f'now is test number => {t_id} | {i}')
        time.sleep(2)
        # r = requests.post('1', json=params, headers=request_head)
        # print(r.text)
    print('任务全部结束 -------')
