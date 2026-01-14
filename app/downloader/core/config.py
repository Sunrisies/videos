"""
配置模块
定义下载器的各种配置参数
"""

import os
import multiprocessing
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class DownloadConfig:
    """下载配置类"""

    # 线程配置
    num_threads: Optional[int] = None

    # 超时配置
    connect_timeout: int = 10
    read_timeout: int = 30

    # 重试配置
    max_retries: int = 3
    retry_delay: float = 1.0  # 秒

    # 下载配置
    chunk_size: int = 8192  # 下载块大小
    buffer_size: int = 1024 * 1024  # 文件写入缓冲区大小

    # 路径配置
    temp_dir: str = "temp"
    output_dir: str = "."

    # 请求头配置
    headers: Dict[str, str] = field(default_factory=lambda: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    # 其他配置
    verify_ssl: bool = False
    show_progress: bool = True
    enable_logging: bool = True

    # ============ 加密相关配置 ============
    # 是否自动解密加密的 TS 片段
    auto_decrypt: bool = True

    # 密钥缓存目录
    key_cache_dir: str = ".key_cache"

    # 密钥缓存有效期（秒）
    key_cache_ttl: int = 3600

    # 自定义密钥路径（如果提供，将使用本地密钥而非从 URI 下载）
    custom_key_path: Optional[str] = None

    # 自定义 IV（十六进制字符串，如 "0x12345678..."）
    custom_iv: Optional[str] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.num_threads is None:
            self.num_threads = multiprocessing.cpu_count() * 2

        # 确保临时目录和输出目录存在
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        # 确保密钥缓存目录存在
        if self.auto_decrypt:
            os.makedirs(self.key_cache_dir, exist_ok=True)

    def update_headers(self, extra_headers: Dict[str, str]):
        """更新请求头"""
        self.headers.update(extra_headers)

    def get_custom_key(self) -> Optional[bytes]:
        """获取自定义密钥"""
        if not self.custom_key_path:
            return None

        try:
            with open(self.custom_key_path, 'rb') as f:
                return f.read()
        except Exception:
            return None

    def get_custom_iv(self) -> Optional[bytes]:
        """获取自定义 IV"""
        if not self.custom_iv:
            return None

        try:
            iv_string = self.custom_iv
            if iv_string.startswith('0x') or iv_string.startswith('0X'):
                iv_string = iv_string[2:]
            return bytes.fromhex(iv_string.zfill(32))
        except Exception:
            return None

    def to_dict(self):
        """转换为字典"""
        return {
            'num_threads': self.num_threads,
            'connect_timeout': self.connect_timeout,
            'read_timeout': self.read_timeout,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'chunk_size': self.chunk_size,
            'buffer_size': self.buffer_size,
            'temp_dir': self.temp_dir,
            'output_dir': self.output_dir,
            'headers': self.headers,
            'verify_ssl': self.verify_ssl,
            'show_progress': self.show_progress,
            'enable_logging': self.enable_logging,
            'auto_decrypt': self.auto_decrypt,
            'key_cache_dir': self.key_cache_dir,
            'key_cache_ttl': self.key_cache_ttl,
            'custom_key_path': self.custom_key_path,
            'custom_iv': self.custom_iv,
        }


# 预设配置模板
class ConfigTemplates:
    """配置模板"""

    @staticmethod
    def fast():
        """快速下载配置"""
        return DownloadConfig(
            num_threads=multiprocessing.cpu_count() * 4,
            max_retries=1,
            retry_delay=0.5,
            connect_timeout=5,
            read_timeout=15,
        )

    @staticmethod
    def stable():
        """稳定下载配置"""
        return DownloadConfig(
            num_threads=multiprocessing.cpu_count(),
            max_retries=5,
            retry_delay=2.0,
            connect_timeout=15,
            read_timeout=60,
        )

    @staticmethod
    def low_bandwidth():
        """低带宽配置"""
        return DownloadConfig(
            num_threads=2,
            max_retries=3,
            retry_delay=3.0,
            chunk_size=4096,
        )

    @staticmethod
    def encrypted():
        """加密流下载配置"""
        return DownloadConfig(
            num_threads=multiprocessing.cpu_count() * 2,
            max_retries=3,
            retry_delay=1.5,
            auto_decrypt=True,
            key_cache_ttl=7200,  # 2 小时缓存
        )

    @staticmethod
    def no_decrypt():
        """不解密配置（仅下载原始加密数据）"""
        return DownloadConfig(
            auto_decrypt=False,
        )
