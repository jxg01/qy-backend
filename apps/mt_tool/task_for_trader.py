from celery import shared_task
import threading
import time
from celery.exceptions import SoftTimeLimitExceeded
from .models import TaskRecord


# @shared_task(bind=True, soft_time_limit=3600)
def execute_parallel_task(self, thread_num, task_num, params, user_id):
    """ Celery任务：执行多线程操作 """
    # 更新任务状态为运行中
    task_record = TaskRecord.objects.get(task_id=self.request.id)
    task_record.status = 'running'
    task_record.save()

    # 创建线程安全的终止标志
    interrupt_flag = threading.Event()
    results = []  # 存储每个线程的结果

    def open_order(n, t_id, flag, results_list):
        """ 订单处理线程 """
        thread_results = []
        for i in range(n + 1):
            if flag.is_set():  # 检查终止标志
                print(f'线程{t_id}被终止')
                results_list.append({
                    'thread_id': t_id,
                    'status': 'cancelled',
                    'progress': f'{i}/{n}'
                })
                return

            print(f'线程{t_id}执行任务 {i}/{n}')
            time.sleep(1)
            # 模拟API调用
            # response = requests.post('https://api.example.com/order', json=params)
            # thread_results.append(response.json())

        print(f'线程{t_id}完成')
        results_list.append({
            'thread_id': t_id,
            'status': 'completed',
            'progress': f'{n}/{n}'
        })

    # 启动线程组
    threads = []
    for x in range(thread_num):
        t = threading.Thread(
            target=open_order,
            args=(task_num, x, interrupt_flag, results)
        )
        t.daemon = True  # 守护线程确保主任务退出时终止
        t.start()
        threads.append(t)

    try:
        # 等待所有线程完成（支持中断）
        for t in threads:
            t.join()

        # 任务成功完成
        task_record.status = 'completed'
        task_record.result = {
            'thread_results': results,
            'message': f'已完成 {thread_num}x{task_num} 个任务'
        }

    except SoftTimeLimitExceeded:
        # 任务超时或被终止
        interrupt_flag.set()  # 通知所有线程终止
        task_record.status = 'cancelled'
        task_record.result = {'error': '任务被用户取消'}

    except Exception as e:
        # 其他异常
        task_record.status = 'failed'
        task_record.result = {'error': str(e)}

    finally:
        task_record.save()
        return task_record.result
