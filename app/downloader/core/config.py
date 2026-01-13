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
    
    def __post_init__(self):
        """初始化后处理"""
        if self.num_threads is None:
            self.num_threads = multiprocessing.cpu_count() * 2
        
        # 确保临时目录和输出目录存在
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
    
    def update_headers(self, extra_headers: Dict[str, str]):
        """更新请求头"""
        self.headers.update(extra_headers)
    
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
