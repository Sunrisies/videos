"""
加密解密模块
支持 AES-128-CBC 加密的 M3U8 流解密
"""

import os
import time
import hashlib
import logging
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import warnings


@dataclass
class EncryptionInfo:
    """加密信息数据类"""
    method: str  # 加密方法: AES-128, SAMPLE-AES, NONE
    uri: Optional[str] = None  # 密钥 URI
    iv: Optional[bytes] = None  # 初始向量 (16 bytes)
    key_format: str = "identity"  # 密钥格式
    key_format_versions: str = ""  # 密钥格式版本

    def is_encrypted(self) -> bool:
        """判断是否加密"""
        return self.method not in (None, "NONE", "")

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'method': self.method,
            'uri': self.uri,
            'iv': self.iv.hex() if self.iv else None,
            'key_format': self.key_format,
            'key_format_versions': self.key_format_versions,
        }


class KeyManager:
    """
    加密密钥管理器

    负责下载、缓存和管理 M3U8 加密密钥
    """

    def __init__(self, cache_dir: str = ".key_cache", cache_ttl: int = 3600):
        """
        初始化密钥管理器

        Args:
            cache_dir: 密钥缓存目录
            cache_ttl: 缓存有效期（秒），默认 1 小时
        """
        self.cache_dir = cache_dir
        self.cache_ttl = cache_ttl
        # (key, timestamp)
        self._memory_cache: Dict[str, Tuple[bytes, float]] = {}
        self._session: Optional[requests.Session] = None
        self.logger = logging.getLogger(__name__)

        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)

    def _get_session(self, verify_ssl: bool = False, headers: Optional[Dict] = None) -> requests.Session:
        """获取或创建 HTTP 会话"""
        if self._session is None:
            self._session = requests.Session()
            self._session.verify = verify_ssl
            if not verify_ssl:
                warnings.filterwarnings(
                    'ignore', category=InsecureRequestWarning)

        if headers:
            self._session.headers.update(headers)

        return self._session

    def _get_cache_key(self, uri: str) -> str:
        """生成缓存键"""
        return hashlib.sha256(uri.encode()).hexdigest()

    def _get_cache_path(self, uri: str) -> str:
        """获取缓存文件路径"""
        cache_key = self._get_cache_key(uri)
        return os.path.join(self.cache_dir, f"{cache_key}.key")

    def _is_cache_valid(self, cache_path: str) -> bool:
        """检查缓存是否有效"""
        if not os.path.exists(cache_path):
            return False

        # 检查文件修改时间
        mtime = os.path.getmtime(cache_path)
        return (time.time() - mtime) < self.cache_ttl

    def get_key(
        self,
        uri: str,
        verify_ssl: bool = False,
        headers: Optional[Dict] = None,
        force_refresh: bool = False
    ) -> Optional[bytes]:
        """
        获取加密密钥

        Args:
            uri: 密钥 URI
            verify_ssl: 是否验证 SSL
            headers: 请求头
            force_refresh: 强制刷新缓存

        Returns:
            bytes: 16 字节密钥，失败返回 None
        """
        if not uri:
            return None

        cache_key = self._get_cache_key(uri)

        # 1. 检查内存缓存
        if not force_refresh and cache_key in self._memory_cache:
            key_data, timestamp = self._memory_cache[cache_key]
            if (time.time() - timestamp) < self.cache_ttl:
                self.logger.debug(f"从内存缓存获取密钥: {uri[:50]}...")
                return key_data

        # 2. 检查文件缓存
        cache_path = self._get_cache_path(uri)
        if not force_refresh and self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    key_data = f.read()

                # 更新内存缓存
                self._memory_cache[cache_key] = (key_data, time.time())
                self.logger.debug(f"从文件缓存获取密钥: {uri[:50]}...")
                return key_data
            except Exception as e:
                self.logger.warning(f"读取缓存密钥失败: {e}")

        # 3. 从网络下载
        try:
            session = self._get_session(verify_ssl, headers)
            response = session.get(uri, timeout=30)
            response.raise_for_status()

            key_data = response.content

            # 验证密钥长度（AES-128 需要 16 字节）
            if len(key_data) != 16:
                self.logger.warning(
                    f"密钥长度异常: {len(key_data)} bytes (期望 16 bytes)")
                # 尝试截取或填充
                if len(key_data) > 16:
                    key_data = key_data[:16]
                else:
                    key_data = key_data.ljust(16, b'\x00')

            # 保存到缓存
            self._save_to_cache(uri, key_data)

            self.logger.info(f"成功下载密钥: {uri[:50]}...")
            return key_data

        except Exception as e:
            self.logger.error(f"下载密钥失败: {uri} - {e}")
            return None

    def _save_to_cache(self, uri: str, key_data: bytes):
        """保存密钥到缓存"""
        cache_key = self._get_cache_key(uri)
        cache_path = self._get_cache_path(uri)

        # 内存缓存
        self._memory_cache[cache_key] = (key_data, time.time())

        # 文件缓存
        try:
            with open(cache_path, 'wb') as f:
                f.write(key_data)
        except Exception as e:
            self.logger.warning(f"保存密钥缓存失败: {e}")

    def clear_cache(self):
        """清除所有缓存"""
        # 清除内存缓存
        self._memory_cache.clear()

        # 清除文件缓存
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.key'):
                    os.remove(os.path.join(self.cache_dir, filename))
            self.logger.info("密钥缓存已清除")
        except Exception as e:
            self.logger.warning(f"清除密钥缓存失败: {e}")

    def preload_key(self, uri: str, verify_ssl: bool = False, headers: Optional[Dict] = None):
        """预加载密钥（异步友好）"""
        self.get_key(uri, verify_ssl, headers)


class AESDecryptor:
    """
    AES-128-CBC 解密器

    用于解密 HLS/M3U8 加密的 TS 片段
    """

    def __init__(self, key_manager: Optional[KeyManager] = None):
        """
        初始化解密器

        Args:
            key_manager: 密钥管理器，如果不提供则创建默认实例
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError(
                "pycryptodome 未安装。请运行: pip install pycryptodome"
            )

        self.key_manager = key_manager or KeyManager()
        self.logger = logging.getLogger(__name__)
        self._current_key: Optional[bytes] = None
        self._current_key_uri: Optional[str] = None

    def set_key(self, key: bytes):
        """
        直接设置解密密钥

        Args:
            key: 16 字节 AES 密钥
        """
        if len(key) != 16:
            raise ValueError(f"AES-128 密钥必须是 16 字节，收到 {len(key)} 字节")
        self._current_key = key
        self._current_key_uri = None

    def load_key_from_uri(
        self,
        uri: str,
        verify_ssl: bool = False,
        headers: Optional[Dict] = None
    ) -> bool:
        """
        从 URI 加载密钥

        Args:
            uri: 密钥 URI
            verify_ssl: 是否验证 SSL
            headers: 请求头

        Returns:
            bool: 是否成功加载
        """
        if uri == self._current_key_uri and self._current_key:
            return True  # 已加载相同密钥

        key = self.key_manager.get_key(uri, verify_ssl, headers)
        if key:
            self._current_key = key
            self._current_key_uri = uri
            return True
        return False

    @staticmethod
    def generate_iv_from_sequence(sequence_number: int) -> bytes:
        """
        根据序列号生成 IV

        HLS 规范：如果没有显式 IV，使用媒体序列号作为 IV

        Args:
            sequence_number: 媒体片段序列号

        Returns:
            bytes: 16 字节 IV
        """
        # 序列号转为 16 字节大端整数
        return sequence_number.to_bytes(16, byteorder='big')

    @staticmethod
    def parse_iv_string(iv_string: str) -> bytes:
        """
        解析 IV 字符串

        Args:
            iv_string: 十六进制 IV 字符串，如 "0x12345678..."

        Returns:
            bytes: 16 字节 IV
        """
        # 移除 0x 前缀
        if iv_string.startswith('0x') or iv_string.startswith('0X'):
            iv_string = iv_string[2:]

        # 确保是 32 个十六进制字符（16 字节）
        iv_string = iv_string.zfill(32)

        return bytes.fromhex(iv_string)

    def decrypt(
        self,
        encrypted_data: bytes,
        iv: Optional[bytes] = None,
        sequence_number: int = 0
    ) -> bytes:
        """
        解密数据

        Args:
            encrypted_data: 加密的数据
            iv: 初始向量，如果为 None 则根据序列号生成
            sequence_number: 片段序列号（当 IV 为 None 时使用）

        Returns:
            bytes: 解密后的数据

        Raises:
            ValueError: 密钥未设置或解密失败
        """
        if not self._current_key:
            raise ValueError("解密密钥未设置")

        # 生成或使用提供的 IV
        if iv is None:
            iv = self.generate_iv_from_sequence(sequence_number)

        try:
            # 创建 AES-CBC 解密器
            cipher = AES.new(self._current_key, AES.MODE_CBC, iv)

            # 解密
            decrypted_data = cipher.decrypt(encrypted_data)

            # 移除 PKCS7 填充
            try:
                decrypted_data = unpad(decrypted_data, AES.block_size)
            except ValueError:
                # 某些流可能没有标准填充，直接返回
                pass

            return decrypted_data

        except Exception as e:
            self.logger.error(f"解密失败: {e}")
            raise ValueError(f"解密失败: {e}")

    def decrypt_segment(
        self,
        encrypted_data: bytes,
        encryption_info: EncryptionInfo,
        sequence_number: int = 0,
        verify_ssl: bool = False,
        headers: Optional[Dict] = None
    ) -> bytes:
        """
        解密 TS 片段（高级接口）

        Args:
            encrypted_data: 加密的片段数据
            encryption_info: 加密信息
            sequence_number: 片段序列号
            verify_ssl: 是否验证 SSL
            headers: 请求头

        Returns:
            bytes: 解密后的数据
        """
        if not encryption_info.is_encrypted():
            return encrypted_data  # 未加密，直接返回

        if encryption_info.method != "AES-128":
            raise ValueError(f"不支持的加密方法: {encryption_info.method}")

        # 加载密钥
        if encryption_info.uri:
            if not self.load_key_from_uri(encryption_info.uri, verify_ssl, headers):
                raise ValueError(f"无法获取解密密钥: {encryption_info.uri}")

        # 解密
        return self.decrypt(
            encrypted_data,
            iv=encryption_info.iv,
            sequence_number=sequence_number
        )


class CryptoHelper:
    """加密辅助工具类"""

    @staticmethod
    def is_crypto_available() -> bool:
        """检查加密库是否可用"""
        return CRYPTO_AVAILABLE

    @staticmethod
    def check_dependencies() -> Dict[str, bool]:
        """检查依赖状态"""
        deps = {
            'pycryptodome': CRYPTO_AVAILABLE,
        }
        return deps

    @staticmethod
    def get_install_instructions() -> str:
        """获取安装说明"""
        if CRYPTO_AVAILABLE:
            return "加密依赖已安装"
        return "请安装 pycryptodome: pip install pycryptodome"
