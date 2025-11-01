#!/usr/bin/env python3
import os
import boto3
from django.conf import settings
import sys
import time

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置Django环境
try:
    # 正确的 Django 环境初始化（适用于 Django 1.4+ 所有版本）
    import django

    # 设置 Django 项目的配置模块路径
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qy_backend.settings")

    # 初始化 Django 环境
    django.setup()
except ImportError:
    print("错误: 无法导入Django设置，请检查项目结构")
    sys.exit(1)

def migrate_media_files():
    """将本地媒体文件迁移到MinIO"""
    # 创建S3客户端
    s3_client = boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL or 'http://127.0.0.1:9000',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or 'admin',
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or '12345678',
        region_name=settings.AWS_S3_REGION_NAME or 'us-east-1',
        config=boto3.session.Config(signature_version='s3v4')
    )
    
    # 原始媒体文件根目录（迁移前的本地路径）
    old_media_root = os.path.join(settings.BASE_DIR, 'media')
    
    if not os.path.exists(old_media_root):
        print(f"本地媒体目录不存在: {old_media_root}")
        print("提示: 如果没有现有媒体文件需要迁移，可以直接使用MinIO")
        return
    
    # 检查存储桶是否存在
    try:
        s3_client.head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
        print(f"确认存储桶存在: {settings.AWS_STORAGE_BUCKET_NAME}")
    except Exception as e:
        print(f"错误: 无法访问存储桶 {settings.AWS_STORAGE_BUCKET_NAME}")
        print(f"请确保MinIO服务正在运行，且存储桶已创建")
        print(f"错误详情: {str(e)}")
        return
    
    # 统计信息
    total_files = 0
    migrated_files = 0
    skipped_files = 0
    failed_files = []
    total_size = 0
    start_time = time.time()
    
    print(f"开始迁移媒体文件从 {old_media_root} 到 MinIO...")
    print(f"目标存储桶: {settings.AWS_STORAGE_BUCKET_NAME}")
    print(f"目标路径前缀: media/")
    print("-" * 80)
    
    # 预先计算文件总数和大小
    print("正在统计文件信息...")
    for root, dirs, files in os.walk(old_media_root):
        total_files += len(files)
        for file_name in files:
            file_path = os.path.join(root, file_name)
            total_size += os.path.getsize(file_path)
    
    print(f"发现 {total_files} 个文件，总计大小: {total_size/1024/1024:.2f} MB")
    print("-" * 80)
    
    # 遍历本地媒体文件
    processed_files = 0
    for root, dirs, files in os.walk(old_media_root):
        for file_name in files:
            processed_files += 1
            
            # 构建本地文件路径
            local_file_path = os.path.join(root, file_name)
            file_size = os.path.getsize(local_file_path)
            
            # 计算相对路径，用于在MinIO中创建相同的目录结构
            relative_path = os.path.relpath(local_file_path, old_media_root)
            s3_key = f"media/{relative_path.replace(os.sep, '/')}"
            
            try:
                # 检查文件是否已存在
                try:
                    s3_client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=s3_key)
                    skipped_files += 1
                    print(f"[{processed_files}/{total_files}] 跳过已存在的文件: {s3_key}")
                    continue
                except:
                    # 文件不存在，继续上传
                    pass
                
                # 上传文件到MinIO
                with open(local_file_path, 'rb') as file_data:
                    s3_client.upload_fileobj(
                        file_data,
                        settings.AWS_STORAGE_BUCKET_NAME,
                        s3_key,
                        ExtraArgs={
                            'ContentType': 'application/octet-stream',
                            'CacheControl': 'max-age=86400'
                        }
                    )
                migrated_files += 1
                progress = (processed_files / total_files) * 100
                elapsed_time = time.time() - start_time
                print(f"[{processed_files}/{total_files}] ({progress:.1f}%) 已迁移: {s3_key} ({file_size/1024:.1f} KB)")
                
            except Exception as e:
                error_msg = f"{local_file_path}: {str(e)}"
                print(f"[{processed_files}/{total_files}] 迁移失败: {error_msg}")
                failed_files.append(error_msg)
    
    # 显示迁移结果
    end_time = time.time()
    duration = end_time - start_time
    
    print("-" * 80)
    print("迁移完成!")
    print(f"总计文件: {total_files}")
    print(f"成功迁移: {migrated_files}")
    print(f"跳过已有: {skipped_files}")
    print(f"迁移失败: {len(failed_files)}")
    print(f"总耗时: {duration:.2f} 秒")
    
    if failed_files:
        print("\n失败文件列表:")
        for i, error in enumerate(failed_files[:10], 1):  # 只显示前10个失败项
            print(f"  {i}. {error}")
        if len(failed_files) > 10:
            print(f"  ... 还有 {len(failed_files) - 10} 个失败项未显示")
    
    print("\n迁移后的文件可以通过以下方式访问:")
    print(f"1. MinIO Web界面: http://127.0.0.1:9001/browser/qy-backend/browse")
    print(f"2. 直接URL格式: http://127.0.0.1:9001/qy-backend/media/[文件路径]")

def verify_minio_connection():
    """验证MinIO连接是否正常"""
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        # 列出存储桶以验证连接
        response = s3_client.list_buckets()
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        
        if settings.AWS_STORAGE_BUCKET_NAME in buckets:
            print(f"✓ 成功连接到MinIO，存储桶 '{settings.AWS_STORAGE_BUCKET_NAME}' 已存在")
            return True
        else:
            print(f"✗ 成功连接到MinIO，但存储桶 '{settings.AWS_STORAGE_BUCKET_NAME}' 不存在")
            print("请先在MinIO中创建存储桶，然后再运行迁移脚本")
            return False
            
    except Exception as e:
        print(f"✗ 无法连接到MinIO服务")
        print(f"错误详情: {str(e)}")
        print("请检查以下事项:")
        print(f"1. MinIO服务是否在 {settings.AWS_S3_ENDPOINT_URL} 运行")
        print(f"2. 访问密钥和密钥是否正确")
        print(f"3. 网络连接是否正常")
        return False

if __name__ == "__main__":
    print("===== Django 媒体文件迁移工具 =====")
    print(f"目标MinIO服务: {settings.AWS_S3_ENDPOINT_URL}")
    print(f"目标存储桶: {settings.AWS_STORAGE_BUCKET_NAME}")
    print()
    
    # 验证MinIO连接
    if not verify_minio_connection():
        print("\n无法继续迁移，请解决连接问题后重试")
        sys.exit(1)
    
    # 询问用户是否继续
    confirm = input("\n是否继续迁移媒体文件？(y/n): ")
    if confirm.lower() != 'y':
        print("迁移已取消")
        sys.exit(0)
    
    # 开始迁移
    migrate_media_files()
    
    print("\n提示: 迁移完成后，您可能需要运行 'python manage.py collectstatic' 来收集静态文件")
    print("请参考 MINIO_CONFIGURATION.md 文档获取更多详细信息")