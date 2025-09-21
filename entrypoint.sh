#!/bin/bash
set -e

# 自动生成 .env 文件（如果不存在）
#/app/generate_env.sh
#bash /app/generate_env.sh

# 等待数据库启动（可选，避免DB还没准备好就迁移）
#echo "Waiting for database..."
#until nc -z $DB_HOST $DB_PORT; do
#  sleep 1
#done
#
#echo "Database is up!"

# 执行迁移
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# 收集静态文件
python manage.py collectstatic --

# 创建超级用户
#if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
#    echo "Creating Django superuser..."
#    python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); \
#if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists(): \
#    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')"
#fi

# 执行原始CMD (supervisord)
# exec "$@"
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
