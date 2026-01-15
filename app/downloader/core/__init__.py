"""
M3U8 Downloader Core Module
核心下载功能模块
"""

from .parser import M3U8Parser, M3U8Info
from .advanced_downloader import (
    AdvancedM3U8Downloader,
    DownloadTask,
    StreamDownloadManager,
    JSONTaskLoader
)
from .config import DownloadConfig, ConfigTemplates
from .crypto import (
    EncryptionInfo,
    KeyManager,
    AESDecryptor,
    CryptoHelper
)
from .progress import (
    MultiTaskProgress,
    SegmentProgressTracker,
    TaskStatus,
    TaskProgress
)
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
    "M3U8Parser",
    "M3U8Info",

    # 高级下载器
    "AdvancedM3U8Downloader",
    "DownloadTask",
    "StreamDownloadManager",
    "JSONTaskLoader",

    # 配置
    "DownloadConfig",
    "ConfigTemplates",

    # 加密支持
    "EncryptionInfo",
    "KeyManager",
    "AESDecryptor",
    "CryptoHelper",

    # 进度显示
    "MultiTaskProgress",
    "SegmentProgressTracker",
    "TaskStatus",
    "TaskProgress",

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
