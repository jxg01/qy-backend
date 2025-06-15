from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, generics
from .models import TaskRecord
from .serializers import TaskRecordSerializer
from .task_for_trader import execute_parallel_task
from celery.result import AsyncResult
from django.contrib.auth import get_user_model

# User = get_user_model()


class TaskAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        启动Celery并行任务
        参数示例：
        {"ts": 1, "tn": 4, "ps": 123}
        """
        # 获取参数
        d = request.data
        thread_num = d.get('ts', 1)
        task_num = d.get('tn', 1)

        # 创建任务记录
        task_record = TaskRecord.objects.create(
            user=request.user,
            parameters=d,
            status='pending'
        )

        # 固定参数（根据需求调整）
        p = {
            "server_name": "abc",
            "trading_account": "123456",
            "key": "P1222",
            "symbol": "AUDUSD"
        }

        # 启动Celery任务
        task = execute_parallel_task.delay(
            thread_num,
            task_num,
            p,
            request.user.id
        )

        # 更新任务记录中的task_id
        task_record.task_id = task.id
        task_record.save()

        return Response({
            'status': '任务已启动',
            'task_id': task.id,
            'monitor_url': f'/api/tasks/{task.id}/',
            'history_url': f'/api/users/{request.user.id}/tasks/'
        }, status=status.HTTP_202_ACCEPTED)

    def delete(self, request, task_id):
        """ 取消任务 """
        try:
            task_record = TaskRecord.objects.get(
                task_id=task_id,
                user=request.user
            )
        except TaskRecord.DoesNotExist:
            return Response({'error': '任务不存在或不属于当前用户'}, status=404)

        # 取消Celery任务
        result = AsyncResult(task_id)
        result.revoke(terminate=True)

        # 更新任务记录状态
        task_record.status = 'cancelled'
        task_record.save()

        return Response({'status': f'任务 {task_id} 已取消'})


class TaskStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        """ 获取任务状态 """
        try:
            task_record = TaskRecord.objects.get(
                task_id=task_id,
                user=request.user
            )
            serializer = TaskRecordSerializer(task_record)
            return Response(serializer.data)
        except TaskRecord.DoesNotExist:
            return Response({'error': '任务不存在'}, status=404)


class UserTaskHistoryView(generics.ListAPIView):
    """ 获取用户的任务历史记录 """
    permission_classes = [IsAuthenticated]
    serializer_class = TaskRecordSerializer

    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        if str(self.request.user.id) != str(user_id):
            return TaskRecord.objects.none()
        return TaskRecord.objects.filter(user_id=user_id).order_by('-created_at')