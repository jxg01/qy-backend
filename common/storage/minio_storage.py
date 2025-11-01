from storages.backends.s3boto3 import S3Boto3Storage
import os


class MinioMediaStorage(S3Boto3Storage):
    """
    自定义MinIO媒体文件存储类
    专门用于处理Django项目中的媒体文件，更好地兼容MinIO存储
    """
    location = 'media'  # 存储路径前缀
    file_overwrite = False  # 不覆盖同名文件
    
    def __init__(self, *args, **kwargs):
        # 从环境变量或Django设置中获取配置
        from django.conf import settings
        
        # 确保使用正确的S3端点URL
        if hasattr(settings, 'AWS_S3_ENDPOINT_URL'):
            kwargs['endpoint_url'] = settings.AWS_S3_ENDPOINT_URL
        
        # 确保使用正确的区域
        if hasattr(settings, 'AWS_S3_REGION_NAME'):
            kwargs['region_name'] = settings.AWS_S3_REGION_NAME
        
        super().__init__(*args, **kwargs)
    
    def get_default_settings(self):
        """获取默认配置，确保兼容MinIO"""
        settings = super().get_default_settings()
        # 确保使用路径样式而不是虚拟主机样式，这对MinIO很重要
        settings['addressing_style'] = 'path'
        return settings
    
    def _clean_name(self, name):
        """清理文件名，确保路径格式正确"""
        # 确保路径使用正斜杠，并且不包含多余的斜杠
        name = super()._clean_name(name)
        return os.path.normpath(name).replace('\\', '/')


class MinioStaticStorage(S3Boto3Storage):
    """
    自定义MinIO静态文件存储类
    专门用于处理Django项目中的静态文件，兼容MinIO存储
    """
    location = 'static'
    file_overwrite = True  # 静态文件可以覆盖