"""
工具模块
包含各种实用工具函数
"""

import os
import sys
import time
import json
import logging
import signal
import warnings
from typing import Dict, List, Optional, Callable
from urllib.parse import urlparse
import hashlib
import requests
from urllib3.exceptions import InsecureRequestWarning


# ==================== 新增: 通用工具函数 ====================

def setup_logger(name: str, log_file: str = 'download.log', console_output: bool = True) -> logging.Logger:
    """
    配置并返回日志记录器

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径
        console_output: 是否输出到控制台

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # 文件 handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

    # 控制台 handler（可选）
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(console_handler)

    return logger


def disable_console_logging(logger: logging.Logger):
    """禁用日志的控制台输出"""
    if logger:
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                logger.removeHandler(handler)


def enable_console_logging(logger: logging.Logger):
    """启用日志的控制台输出"""
    if logger:
        # 检查是否已有 StreamHandler
        has_console = any(
            isinstance(h, logging.StreamHandler) and not isinstance(
                h, logging.FileHandler)
            for h in logger.handlers
        )
        if not has_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(console_handler)


def create_session(verify_ssl: bool = False, headers: Optional[Dict[str, str]] = None) -> requests.Session:
    """
    创建配置好的 HTTP 会话

    Args:
        verify_ssl: 是否验证 SSL 证书
        headers: 自定义请求头

    Returns:
        requests.Session: 配置好的会话对象
    """
    session = requests.Session()
    session.verify = verify_ssl

    if not verify_ssl:
        warnings.filterwarnings('ignore', category=InsecureRequestWarning)

    if headers:
        session.headers.update(headers)

    return session


def extract_filename_from_url(url: str) -> str:
    """
    从 URL 提取文件名,移除查询参数和片段标识

    Args:
        url: URL 字符串

    Returns:
        str: 文件名
    """
    clean_url = url.split('?')[0].split('#')[0]
    return clean_url.split('/')[-1]


def format_progress(completed: int, total: int, failed: int = 0) -> str:
    """
    格式化进度字符串

    Args:
        completed: 已完成数量
        total: 总数量
        failed: 失败数量

    Returns:
        str: 格式化后的进度字符串
    """
    if failed > 0:
        return f"{completed}/{total} 完成, {failed} 失败"
    return f"{completed}/{total} 完成"


class RetryHandler:
    """
    重试处理器 - 支持指数退避策略

    从 downloader.py 移动到 utils.py 作为通用工具类
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        初始化重试处理器

        Args:
            max_retries: 最大重试次数
            retry_delay: 重试延迟(秒)
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def execute_with_retry(self, func: Callable, *args, **kwargs):
        """
        执行函数,失败时重试

        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            Exception: 重试失败后抛出最后一次的异常
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    # 指数退避
                    time.sleep(self.retry_delay * (2 ** attempt))
                else:
                    raise last_exception

        raise last_exception


# ==================== 原有工具类 ====================


class ProgressTracker:
    """进度跟踪器"""

    def __init__(self, total: int, description: str = "进度"):
        self.total = total
        self.completed = 0
        self.failed = 0
        self.description = description
        self.start_time = time.time()
        self.last_update = time.time()

    def update(self, success: bool = True):
        """更新进度"""
        if success:
            self.completed += 1
        else:
            self.failed += 1
        self.last_update = time.time()

    def get_progress(self) -> Dict:
        """获取当前进度信息"""
        elapsed = time.time() - self.start_time
        speed = (self.completed + self.failed) / elapsed if elapsed > 0 else 0

        return {
            'completed': self.completed,
            'failed': self.failed,
            'total': self.total,
            'percentage': (self.completed + self.failed) / self.total * 100 if self.total > 0 else 0,
            'speed': speed,
            'elapsed': elapsed,
            'eta': (self.total - self.completed - self.failed) / speed if speed > 0 else 0,
        }

    def __str__(self):
        info = self.get_progress()
        return (f"{self.description}: {info['completed']}/{info['total']} "
                f"({info['percentage']:.1f}%) - "
                f"失败: {info['failed']} - "
                f"速度: {info['speed']:.1f} files/s - "
                f"预计剩余: {info['eta']:.1f}s")


class FileValidator:
    """文件验证器"""

    @staticmethod
    def validate_url(url: str) -> bool:
        """验证URL格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    @staticmethod
    def validate_m3u8_content(content: str) -> bool:
        """验证M3U8内容格式"""
        if not content:
            return False

        lines = content.strip().split('\n')
        if not lines:
            return False

        # 检查是否包含M3U8标记
        first_line = lines[0].strip()
        if not first_line.startswith('#EXTM3U'):
            return False

        # 检查是否有TS文件或子M3U8
        has_media = any(line.strip().endswith(('.ts', '.m3u8'))
                        for line in lines if not line.startswith('#'))

        return has_media

    @staticmethod
    def check_disk_space(required_size: int, path: str = ".") -> bool:
        """检查磁盘空间"""
        try:
            import shutil
            stat = shutil.disk_usage(path)
            return stat.free > required_size
        except:
            return True  # 如果无法检查，假设有足够空间


class URLProcessor:
    """URL处理器"""

    @staticmethod
    def normalize_url(url: str) -> str:
        """标准化URL"""
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url

    @staticmethod
    def extract_domain(url: str) -> str:
        """提取域名"""
        try:
            return urlparse(url).netloc
        except:
            return ""

    @staticmethod
    def append_query_params(url: str, params: Dict[str, str]) -> str:
        """添加查询参数"""
        from urllib.parse import urlencode, urlparse, urlunparse

        parsed = urlparse(url)
        existing_params = {}

        if parsed.query:
            for pair in parsed.query.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    existing_params[key] = value

        existing_params.update(params)

        new_query = urlencode(existing_params)

        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))


class CacheManager:
    """缓存管理器"""

    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_cache_path(self, key: str) -> str:
        """获取缓存文件路径"""
        # 使用hash生成文件名
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{hash_key}.json")

    def save_cache(self, key: str, data: any) -> bool:
        """保存缓存"""
        try:
            cache_path = self.get_cache_path(key)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'data': data,
                    'timestamp': time.time()
                }, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False

    def load_cache(self, key: str, max_age: int = 3600) -> Optional[any]:
        """加载缓存"""
        try:
            cache_path = self.get_cache_path(key)
            if not os.path.exists(cache_path):
                return None

            with open(cache_path, 'r', encoding='utf-8') as f:
                cached = json.load(f)

            # 检查缓存是否过期
            if time.time() - cached['timestamp'] > max_age:
                return None

            return cached['data']
        except:
            return None

    def clear_cache(self):
        """清除所有缓存"""
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    os.remove(os.path.join(self.cache_dir, filename))
        except:
            pass


class Statistics:
    """统计信息"""

    def __init__(self):
        self.data = {}

    def add(self, key: str, value: any):
        """添加统计"""
        if key not in self.data:
            self.data[key] = []
        self.data[key].append(value)

    def get_average(self, key: str) -> float:
        """获取平均值"""
        if key not in self.data or not self.data[key]:
            return 0
        return sum(self.data[key]) / len(self.data[key])

    def get_total(self, key: str) -> float:
        """获取总和"""
        if key not in self.data:
            return 0
        return sum(self.data[key])

    def get_count(self, key: str) -> int:
        """获取数量"""
        if key not in self.data:
            return 0
        return len(self.data[key])

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            key: {
                'total': self.get_total(key),
                'average': self.get_average(key),
                'count': self.get_count(key),
            }
            for key in self.data
        }


def format_file_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def format_time(seconds: float) -> str:
    """格式化时间"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def print_banner():
    """打印欢迎横幅"""
    banner = """
        ╔══════════════════════════════════════════════════════════════╗
        ║                  M3U8 Downloader Pro v2.2.2                  ║
        ║                                                              ║
        ║  高性能M3U8视频下载器                                        ║
        ║  支持多线程、断点续传、错误重试、智能解析                    ║
        ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def confirm_action(message: str) -> bool:
    """确认操作"""
    response = input(f"{message} [y/N]: ").strip().lower()
    return response in ['y', 'yes']


def safe_input(prompt: str, default: str = "") -> str:
    """安全输入"""
    try:
        value = input(prompt).strip()
        return value if value else default
    except (KeyboardInterrupt, EOFError):
        return default

def check_ts_header(file_path):
    """检查TS文件头部是否正常"""
    try:
        if not os.path.exists(file_path):
            return False
            
        with open(file_path, 'rb') as f:
            # 读取前188字节（一个TS包的大小）
            header = f.read(188)
            if len(header) < 4:
                return False
                
            # 标准TS包以0x47开头
            if header[0] == 0x47:
                # 进一步验证：检查是否连续多个TS包都以0x47开头
                # 读取更多数据验证
                f.seek(0)
                sample_data = f.read(min(1880, os.path.getsize(file_path)))  # 读取前10个TS包
                if len(sample_data) >= 188:
                    # 检查前几个TS包的同步字节
                    valid_count = sum(1 for i in range(0, min(len(sample_data), 1880), 188) 
                                     if i < len(sample_data) and sample_data[i] == 0x47)
                    # 至少前3个包应该是有效的
                    return valid_count >= 3
                return True
            else:
                return False
    except Exception as e:
        return False


def extract_filename(url: str) -> str:
    """从URL提取文件名"""
    # 使用 utils.py 中的 extract_filename_from_url 函数
    return extract_filename_from_url(url)