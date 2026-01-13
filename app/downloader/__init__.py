"""
M3U8 Downloader Package
一个模块化的M3U8视频下载器，支持多线程下载、断点续传、错误重试、JSON配置等功能
"""

from .core.downloader import M3U8Downloader, DownloadManager
from .core.parser import M3U8Parser
from .core.config import DownloadConfig, ConfigTemplates
from .core.advanced_downloader import (
    AdvancedM3U8Downloader, 
    DownloadTask, 
    StreamDownloadManager,
    JSONTaskLoader
)
from .core.utils import (
    FileValidator, 
    URLProcessor, 
    CacheManager, 
    Statistics,
    format_file_size,
    format_time,
    print_banner
)

__version__ = "2.1.0"
__all__ = [
    # 基础功能
    "M3U8Downloader",
    "M3U8Parser", 
    "DownloadManager",
    "DownloadConfig",
    "ConfigTemplates",
    
    # 高级功能
    "AdvancedM3U8Downloader",
    "DownloadTask",
    "StreamDownloadManager", 
    "JSONTaskLoader",
    
    # 工具类
    "FileValidator",
    "URLProcessor",
    "CacheManager",
    "Statistics",
    "format_file_size",
    "format_time",
    "print_banner"
]
