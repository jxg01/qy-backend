# 使用官方 Python 镜像作为基础镜像
FROM python:3.10-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=qy_backend.settings

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential gcc libssl-dev libpq-dev \
    nginx supervisor curl \
    default-libmysqlclient-dev \
 && rm -rf /var/lib/apt/lists/*

# 升级 pip 并安装 uwsgi
RUN python -m pip install --upgrade pip \
 && pip install uwsgi

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . /app/

# 复制配置文件
COPY uwsgi.ini /app/
COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf


# 创建需要的目录并赋予权限
RUN mkdir -p /app/staticfiles /app/media /app/logs \
 && mkdir -p /var/lib/nginx /var/lib/nginx/body /run/nginx \
 && chown -R www-data:www-data /app /var/lib/nginx /run/nginx /var/log/nginx

# 收集静态文件
RUN python manage.py collectstatic --noinput || true

# 暴露端口
EXPOSE 80

# 执行数据库迁移
COPY entrypoint.sh /entrypoint.sh
# COPY generate_env.sh /app/generate_env.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# 使用 supervisor 管理 uwsgi + nginx
# CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
