# 使用官方 Python 镜像作为基础镜像
FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy

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

# 升级 pip
RUN python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip

# 安装 uvicorn,支持ws
RUN pip install "uvicorn[standard]"

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . /app/

# 复制配置文件
COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf


# 创建需要的目录并赋予权限
RUN mkdir -p /app/staticfiles /app/media /app/logs/{celery,django} \
 && mkdir -p /var/lib/nginx /var/lib/nginx/body /run/nginx \
 && chown -R www-data:www-data /app /var/lib/nginx /run/nginx /var/log/nginx \
 && chmod -R 755 /app/logs

# 暴露端口
EXPOSE 80

# entrypoint文件执行python manage.py migrate等命令
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
