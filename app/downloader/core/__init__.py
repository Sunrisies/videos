"""
M3U8 Downloader Core Module
核心下载功能模块
"""

from .downloader import M3U8Downloader, DownloadManager
from .parser import M3U8Parser
from .advanced_downloader import (
    AdvancedM3U8Downloader,
    DownloadTask,
    StreamDownloadManager,
    JSONTaskLoader
)
from .config import DownloadConfig, ConfigTemplates
from .utils import (
    FileValidator,
    URLProcessor,
    CacheManager,
    Statistics,
    format_file_size,
    format_time,
    print_banner,
    RetryHandler,
    setup_logger,
    create_session,
    extract_filename_from_url,
    format_progress
)

__all__ = [
    # 基础下载器
    "M3U8Downloader",
    "DownloadManager",
    "M3U8Parser",
    
    # 高级下载器
    "AdvancedM3U8Downloader",
    "DownloadTask",
    "StreamDownloadManager",
    "JSONTaskLoader",
    
    # 配置
    "DownloadConfig",
    "ConfigTemplates",
    
    # 工具函数
    "FileValidator",
    "URLProcessor",
    "CacheManager",
    "Statistics",
    "format_file_size",
    "format_time",
    "print_banner",
    "RetryHandler",
    "setup_logger",
    "create_session",
    "extract_filename_from_url",
    "format_progress"
]
