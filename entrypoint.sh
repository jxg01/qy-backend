#!/bin/bash
set -e

# 等待数据库（简单重试）
until python - <<'PY'
import os, pymysql, time
import sys
from pymysql import Error

# 获取当前目录路径
current_dir = os.getcwd()
print(f"当前目录: {current_dir}")

# 列出目录内容
print("\n目录内容:")
for item in os.listdir(current_dir):
    item_path = os.path.join(current_dir, item)
    print(f"- {'[目录]' if os.path.isdir(item_path) else '[文件]'} {item}")

# dsn = f"dbname={os.getenv('DB_NAME','easy_api')} user={os.getenv('DB_USER','root')} password={os.getenv('DB_PASSWORD','12345678')} host={os.getenv('DB_HOST','mysql')}"
dsn = {"host": os.getenv('DB_HOST','mysql'), "port": int(os.getenv('DB_PORT',3306)), "user": os.getenv('DB_USER','root'), "password": os.getenv('DB_PASSWORD','12345678'), "database": os.getenv('DB_NAME','easy_api'), "charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor}
print("dsn => ", dsn)
for i in range(30):
    try:
        # pymysql.connect(host='127.0.0.1',user='root',password='12345678',database='easy_api',port=3306,charset='utf8mb4',cursorclass=pymysql.cursors.DictCursor)
        pymysql.connect(**dsn)
        sys.exit(0)
    except Error as e:
        print(f"数据库连接失败: {e}")
        time.sleep(1)
sys.exit(1)
PY
do
  echo "DB not ready, retrying..."
done

# 执行迁移
# python manage.py makemigrations --noinput
python manage.py migrate --noinput

# 收集静态文件
python manage.py collectstatic --noinput

# 创建超级用户
#if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
#    echo "Creating Django superuser..."
#    python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); \
#if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists(): \
#    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')"
#fi

# 执行原始CMD (supervisord)
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
