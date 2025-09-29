#!/bin/bash
set - e

echo
"Starting Celery..."

# 等待服务就绪
echo
"Waiting for database and redis..."
until
python - c
"
import os, pymysql, time, redis
from pymysql import Error

# 数据库配置
db_config = {
    'host': os.getenv('DB_HOST', 'mysql'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '12345678'),
    'database': os.getenv('DB_NAME', 'easy_api'),
    'charset': 'utf8mb4'
}

for i in range(30):
    try:
        # 测试数据库连接
        conn = pymysql.connect(**db_config)
        conn.close()

        # 测试 Redis 连接
        r = redis.Redis(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0))
        )
        r.ping()

        print('All services are ready!')
        break
    except Exception as e:
        if i == 29:
            echo
            'Services not ready, exiting...'
            exit
            1
        echo
        'Services not ready, retrying...'
        sleep
        2
done

# 启动 Celery
if ["$1" = "worker"]; then
echo
"Starting Celery Worker..."
exec celery -A qy_backend worker --loglevel=info
elif ["$1" = "beat"]; then
echo
"Starting Celery Beat..."
# 确保日志目录存在
mkdir - p /app/logs/celery
exec celery -A qy_backend beat --loglevel=info --logfile=/app/logs/celery/celery-beat.log
else
echo
"Unknown command: $1"
exit
1
fi
