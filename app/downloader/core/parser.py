"""
M3U8解析器模块
负责解析M3U8文件，提取TS文件URL列表
支持加密 M3U8 的 #EXT-X-KEY 标签解析
"""

import re
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional, Tuple
import requests
import warnings

from urllib3.exceptions import InsecureRequestWarning

from .crypto import EncryptionInfo


class M3U8Parser:
    """M3U8文件解析器"""

    def __init__(self, verify_ssl: bool = False):
        self.verify_ssl = verify_ssl
        if not verify_ssl:
            warnings.filterwarnings('ignore', category=InsecureRequestWarning)

        self.session = requests.Session()
        self.session.verify = verify_ssl

    def parse_m3u8(self, url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[List[str], Dict]:
        """
        解析M3U8文件

        Args:
            url: M3U8文件URL
            headers: 请求头

        Returns:
            Tuple[List[str], Dict]: (TS文件URL列表, 解析信息)
        """
        try:
            if headers:
                self.session.headers.update(headers)

            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # 获取基础URL
            base_url = url.rsplit('/', 1)[0] + '/'

            # 解析M3U8内容
            content = response.text
            ts_files = []
            resolution_info = {}
            bandwidth_info = {}

            # 解析加密信息
            encryption_info = self._parse_encryption_key(content, base_url)

            # 提取分辨率和带宽信息
            for line in content.split('\n'):
                if line.startswith('#EXT-X-STREAM-INF'):
                    # 解析流媒体信息
                    resolution_match = re.search(r'RESOLUTION=(\d+x\d+)', line)
                    bandwidth_match = re.search(r'BANDWIDTH=(\d+)', line)

                    if resolution_match:
                        resolution_info['resolution'] = resolution_match.group(
                            1)
                    if bandwidth_match:
                        bandwidth_info['bandwidth'] = int(
                            bandwidth_match.group(1))

            # 提取媒体序列号（用于 IV 生成）
            media_sequence = self._parse_media_sequence(content)

            # 提取TS文件
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    if line.endswith('.ts') or '.ts?' in line:
                        # 完整URL
                        if line.startswith('http'):
                            ts_files.append(line)
                        else:
                            # 相对路径
                            ts_files.append(urljoin(base_url, line))
                    elif line.endswith('.m3u8') or '.m3u8?' in line:
                        # 嵌套的M3U8，递归处理（这里简化处理，直接作为TS文件）
                        if line.startswith('http'):
                            ts_files.append(line)
                        else:
                            ts_files.append(urljoin(base_url, line))

            # 解析信息
            parse_info = {
                'total_segments': len(ts_files),
                'base_url': base_url,
                'resolution': resolution_info.get('resolution', 'N/A'),
                'bandwidth': bandwidth_info.get('bandwidth', 'N/A'),
                'content_length': len(content),
                'encryption': encryption_info.to_dict() if encryption_info else None,
                'is_encrypted': encryption_info.is_encrypted() if encryption_info else False,
                'media_sequence': media_sequence,
            }

            return ts_files, parse_info

        except Exception as e:
            raise Exception(f"M3U8解析失败: {e}")

    def _parse_encryption_key(self, content: str, base_url: str) -> Optional[EncryptionInfo]:
        """
        解析 #EXT-X-KEY 标签

        格式示例:
        #EXT-X-KEY:METHOD=AES-128,URI="https://example.com/key.key",IV=0x12345678...

        Args:
            content: M3U8 文件内容
            base_url: 基础 URL（用于相对路径转换）

        Returns:
            EncryptionInfo: 加密信息，如果未加密返回 None
        """
        # 查找 #EXT-X-KEY 标签
        key_pattern = r'#EXT-X-KEY:(.+)'
        match = re.search(key_pattern, content)

        if not match:
            return None

        key_attrs = match.group(1)

        # 解析 METHOD
        method_match = re.search(r'METHOD=([^,\s]+)', key_attrs)
        method = method_match.group(1) if method_match else "NONE"

        if method == "NONE":
            return EncryptionInfo(method="NONE")

        # 解析 URI
        uri_match = re.search(r'URI="([^"]+)"', key_attrs)
        uri = None
        if uri_match:
            uri_value = uri_match.group(1)
            # 处理相对路径
            if not uri_value.startswith('http'):
                uri = urljoin(base_url, uri_value)
            else:
                uri = uri_value

        # 解析 IV
        iv = None
        iv_match = re.search(r'IV=([^,\s]+)', key_attrs)
        if iv_match:
            iv_string = iv_match.group(1)
            try:
                # 移除 0x 前缀并转换为 bytes
                if iv_string.startswith('0x') or iv_string.startswith('0X'):
                    iv_string = iv_string[2:]
                iv = bytes.fromhex(iv_string.zfill(32))
            except ValueError:
                iv = None

        # 解析 KEYFORMAT
        keyformat_match = re.search(r'KEYFORMAT="([^"]+)"', key_attrs)
        key_format = keyformat_match.group(
            1) if keyformat_match else "identity"

        # 解析 KEYFORMATVERSIONS
        keyformat_versions_match = re.search(
            r'KEYFORMATVERSIONS="([^"]+)"', key_attrs)
        key_format_versions = keyformat_versions_match.group(
            1) if keyformat_versions_match else ""

        return EncryptionInfo(
            method=method,
            uri=uri,
            iv=iv,
            key_format=key_format,
            key_format_versions=key_format_versions
        )

    def _parse_media_sequence(self, content: str) -> int:
        """
        解析媒体序列号

        #EXT-X-MEDIA-SEQUENCE:0

        Args:
            content: M3U8 文件内容

        Returns:
            int: 媒体序列号起始值
        """
        match = re.search(r'#EXT-X-MEDIA-SEQUENCE:(\d+)', content)
        return int(match.group(1)) if match else 0

    def parse_m3u8_extended(self, url: str, headers: Optional[Dict[str, str]] = None) -> 'M3U8Info':
        """
        扩展解析方法，返回 M3U8Info 对象

        Args:
            url: M3U8 文件 URL
            headers: 请求头

        Returns:
            M3U8Info: 完整的 M3U8 信息对象
        """
        ts_files, parse_info = self.parse_m3u8(url, headers)
        return M3U8Info(url, ts_files, parse_info)

    def validate_url(self, url: str) -> bool:
        """验证URL格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    def get_url_info(self, url: str) -> Dict:
        """获取URL信息"""
        try:
            parsed = urlparse(url)
            return {
                'scheme': parsed.scheme,
                'netloc': parsed.netloc,
                'path': parsed.path,
                'query': parsed.query,
                'fragment': parsed.fragment,
            }
        except:
            return {}

    def extract_base_url(self, url: str) -> str:
        """提取基础URL"""
        return url.rsplit('/', 1)[0] + '/'

    def is_m3u8_url(self, url: str) -> bool:
        """判断是否为M3U8 URL"""
        return url.endswith('.m3u8') or '.m3u8?' in url.lower()


class M3U8Info:
    """M3U8信息容器"""

    def __init__(self, url: str, ts_files: List[str], parse_info: Dict):
        self.url = url
        self.ts_files = ts_files
        self.total_segments = parse_info.get('total_segments', 0)
        self.base_url = parse_info.get('base_url', '')
        self.resolution = parse_info.get('resolution', 'N/A')
        self.bandwidth = parse_info.get('bandwidth', 'N/A')
        self.content_length = parse_info.get('content_length', 0)
        self.is_encrypted = parse_info.get('is_encrypted', False)
        self.encryption = parse_info.get('encryption')
        self.media_sequence = parse_info.get('media_sequence', 0)

    def __str__(self):
        encryption_status = "AES-128 加密" if self.is_encrypted else "未加密"
        return f"""M3U8 Information:
    URL: {self.url}
    Total Segments: {self.total_segments}
    Base URL: {self.base_url}
    Resolution: {self.resolution}
    Bandwidth: {self.bandwidth}
    Content Length: {self.content_length} bytes
    Encryption: {encryption_status}
    Media Sequence: {self.media_sequence}"""

    def to_dict(self):
        """转换为字典"""
        return {
            'url': self.url,
            'total_segments': self.total_segments,
            'base_url': self.base_url,
            'resolution': self.resolution,
            'bandwidth': self.bandwidth,
            'content_length': self.content_length,
            'ts_files': self.ts_files[:10],  # 只显示前10个
            'is_encrypted': self.is_encrypted,
            'encryption': self.encryption,
            'media_sequence': self.media_sequence,
        }

    def get_encryption_info(self) -> Optional[EncryptionInfo]:
        """获取加密信息对象"""
        if not self.encryption:
            return None

        return EncryptionInfo(
            method=self.encryption.get('method', 'NONE'),
            uri=self.encryption.get('uri'),
            iv=bytes.fromhex(self.encryption['iv']) if self.encryption.get(
                'iv') else None,
            key_format=self.encryption.get('key_format', 'identity'),
            key_format_versions=self.encryption.get('key_format_versions', '')
        )
