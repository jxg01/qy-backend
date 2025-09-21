#!/bin/bash
# generate_env.sh
set -e

ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Creating default .env file..."
  cat > "$ENV_FILE" <<EOF
# Django settings
DEBUG=False
DJANGO_SETTINGS_MODULE=qy_backend.settings
SECRET_KEY=$(openssl rand -hex 32)

# Database
DB_HOST=mysql
DB_PORT=33061
DB_NAME=easy_api
DB_USER=root
DB_PASSWORD=12345678

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Django superuser
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@qq.com
DJANGO_SUPERUSER_PASSWORD=admin123
EOF

  echo ".env file created successfully."
else
  echo ".env file already exists, skipping..."
fi
