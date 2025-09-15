# qy-backend
后端项目

# Django DRF 自动化测试平台 Docker部署指南

本指南将帮助您使用Docker部署Django DRF自动化测试平台。

## 准备工作

1. 确保您的服务器上已安装Docker和Docker Compose

2. 克隆项目代码到您的服务器

3. 修改.env文件中的配置（特别是密码和密钥）：
   ```bash
   # 编辑.env文件
   nano .env
   ```
   请至少修改以下值：
   - SECRET_KEY：设置为一个随机的、安全的字符串
   - DB_PASSWORD：设置数据库用户密码
   - MYSQL_ROOT_PASSWORD：设置MySQL root用户密码

   完整的环境变量配置示例如下：

   ```env
   # Django settings
   DEBUG=True
   SECRET_KEY=your-secret-key-for-production

   # Database settings
   DB_NAME=easy_api
   DB_USER=admin
   DB_PASSWORD=your-database-password
   DB_HOST=db
   DB_PORT=3306
   MYSQL_ROOT_PASSWORD=your-root-password

   # Redis settings
   REDIS_HOST=redis
   REDIS_PORT=6379

   # Celery settings
   CELERY_BROKER_URL=redis://redis:6379/0
   CELERY_RESULT_BACKEND=redis://redis:6379/1
   ```

   #### 本地开发配置

   对于本地开发环境，您可以创建一个 `.env.local` 文件来覆盖 `.env` 中的设置，使本地开发更加方便：

   ```env
   # Local development settings (override .env)

   # Use localhost for database in local development
   DB_HOST=127.0.0.1

   # Use localhost for Redis in local development
   REDIS_HOST=127.0.0.1

   # Update Celery settings for local development
   CELERY_BROKER_URL=redis://127.0.0.1:6379/0
   CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1
   ```

   **注意**：`.env.local` 文件已经在 `.gitignore` 中配置为忽略，不会被提交到版本控制系统中，因此您可以在其中添加本地开发的特定配置。

   当您在本地运行 `python3 manage.py runserver` 或其他 Django 命令时，系统会优先读取 `.env.local` 文件中的配置，然后再读取 `.env` 文件中的配置，确保本地开发环境使用正确的数据库和 Redis 连接信息。

   ### 本地开发环境中启动Celery

   在本地开发环境中，您可以按照以下步骤启动Celery worker和beat服务，确保日志能够正常写入文件：

   #### 前置条件

   1. 确保本地已安装Redis服务并启动
   2. 确保项目根目录下的`.env.local`文件已正确配置本地Redis连接信息：
      ```env
      # Local development settings (override .env)
      DB_HOST=127.0.0.1
      REDIS_HOST=127.0.0.1
      CELERY_BROKER_URL=redis://127.0.0.1:6379/0
      CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1
      ```

   #### 启动Celery Worker

   在项目根目录下打开一个终端，执行以下命令：

   ```bash
   celery -A qy-backend worker --loglevel=info
   ```

   此命令会：
   - 启动Celery worker进程
   - 使用项目中的日志配置（TimedRotatingFileHandler，每天午夜切割日志）
   - 将日志同时输出到控制台和`logs/celery/celery-worker.log`文件

   #### 启动Celery Beat

   在项目根目录下再打开一个终端，执行以下命令：

   ```bash
   celery -A qy-backend beat --loglevel=info
   ```

   此命令会：
   - 启动Celery beat进程（用于调度定时任务）
   - 使用项目中的日志配置（TimedRotatingFileHandler，每天午夜切割日志）
   - 将日志同时输出到控制台和`logs/celery/celery-beat.log`文件

   #### 注意事项

   1. **自动创建日志目录**：项目代码会自动创建日志目录（`logs/celery/`和`logs/django/`），无需手动创建
   2. **日志轮转**：日志文件会按照settings.py中的配置自动按日期轮转，并保留30天历史日志
   3. **环境变量优先级**：本地开发时，`.env.local`文件中的配置会覆盖`.env`文件中的配置
   4. **日志查看**：您可以通过以下命令查看实时日志输出：
      ```bash
      tail -f logs/celery/celery-worker.log
      tail -f logs/celery/celery-beat.log
      ```

   #### 自定义日志级别

   如果需要调整日志级别，可以在启动命令中修改`--loglevel`参数：

   ```bash
   # 更多日志信息（DEBUG级别）
   celery -A qy-backend worker --loglevel=debug

   # 更少日志信息（WARNING级别）
   celery -A qy-backend worker --loglevel=warning
   ```

   #### Celery日志配置说明

   项目已经在`qy-backend/celery.py`中添加了专门的日志配置代码：
   ```python
   # 配置 Celery 使用 Django 的日志设置
   # 这将确保 Celery 使用 settings.py 中配置的日志处理器
   # 包括文件输出和按日期轮转的功能
   logging.config.dictConfig(settings.LOGGING)
   ```

   这个设置确保了：
   1. Celery 会使用 `settings.py` 中定义的 `LOGGING` 配置
   2. 日志会同时输出到控制台和文件中
   3. 日志文件会按照配置自动按日期轮转

   **重要提示**：请确保 `logs/celery/` 目录有正确的写入权限，否则日志文件可能无法正常写入。

4. 修改mysql-init/init.sql文件中的密码，使其与.env文件中的密码保持一致：
   ```bash
   nano mysql-init/init.sql
   ```

## 部署步骤

1. 构建并启动所有容器：
   ```bash
   docker-compose up -d --build
   ```

2. 执行数据库迁移：
   ```bash
   docker-compose exec web python manage.py migrate
   ```

3. 创建超级用户：
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

4. 收集静态文件（如果还没有在Dockerfile中完成）：
   ```bash
   docker-compose exec web python manage.py collectstatic --noinput
   ```

## 验证部署

1. 检查所有容器是否正常运行：
   ```bash
   docker-compose ps
   ```

2. 访问应用：
   打开浏览器，访问 `http://服务器IP:8000`
   管理后台地址：`http://服务器IP:8000/admin`

## 常用命令

### 查看容器日志
```bash
# 查看Web应用日志
docker-compose logs web

# 查看MySQL日志
docker-compose logs db

# 查看Redis日志
docker-compose logs redis

# 查看Celery Worker日志
docker-compose logs celery_worker
# 或直接查看宿主机上的最新日志文件
cat logs/celery/celery-worker.log
# 查看历史日志文件
ls -l logs/celery/
cat logs/celery/celery-worker.log.2025-02-10

# 查看Celery Beat日志
docker-compose logs celery_beat
# 或直接查看宿主机上的最新日志文件
cat logs/celery/celery-beat.log
# 查看历史日志文件
ls -l logs/celery/
cat logs/celery/celery-beat.log.2025-02-10
```

### 进入容器
```bash
# 进入Web应用容器
docker-compose exec web bash

# 进入MySQL容器
docker-compose exec db mysql -u root -p
```

### 停止和重启服务
```bash
# 停止所有服务
docker-compose down

# 重启所有服务
docker-compose restart
```

## 注意事项

1. 在生产环境中，建议：
   - 设置DEBUG=False
   - 使用更安全的SECRET_KEY
   - 配置HTTPS（可以使用Nginx作为反向代理，并配置SSL证书）

2. 数据持久化：
   - MySQL数据存储在mysql_data卷中
   - Redis数据存储在redis_data卷中
   - 静态文件和媒体文件分别存储在./staticfiles和./media目录中
   - Celery日志文件存储在./logs/celery目录中

3. 如果需要修改Django设置，建议在.env文件中添加环境变量，然后在settings.py中使用os.getenv()读取。

4. 定期备份数据库和重要数据。

5. Celery日志配置：
   - 日志文件路径：./logs/celery/
   - Worker日志：celery-worker.log（按日期自动轮转，例如：celery-worker.log.2025-02-10）
   - Beat日志：celery-beat.log（按日期自动轮转，例如：celery-beat.log.2025-02-10）
   - 日志轮转配置：每天午夜自动切割，保留30天历史日志
   - 日志级别可在docker-compose.yml中的command参数中修改
   - 如需调整日志格式或轮转策略，可以在settings.py中的LOGGING配置中修改

6. 日志管理提示：
   - 由于日志会按日期自动轮转，可以定期归档或清理旧的日志文件
   - 可以使用日志分析工具（如logrotate）进一步管理日志文件
   - 监控日志文件大小，确保磁盘空间充足