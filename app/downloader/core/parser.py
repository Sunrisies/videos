"""
M3U8解析器模块
负责解析M3U8文件，提取TS文件URL列表
"""

import re
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional, Tuple
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import warnings


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
            
            # 提取分辨率和带宽信息
            for line in content.split('\n'):
                if line.startswith('#EXT-X-STREAM-INF'):
                    # 解析流媒体信息
                    resolution_match = re.search(r'RESOLUTION=(\d+x\d+)', line)
                    bandwidth_match = re.search(r'BANDWIDTH=(\d+)', line)
                    
                    if resolution_match:
                        resolution_info['resolution'] = resolution_match.group(1)
                    if bandwidth_match:
                        bandwidth_info['bandwidth'] = int(bandwidth_match.group(1))
            
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
            }
            
            return ts_files, parse_info
            
        except Exception as e:
            raise Exception(f"M3U8解析失败: {e}")
    
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
    
    def __str__(self):
        return f"""M3U8 Information:
    URL: {self.url}
    Total Segments: {self.total_segments}
    Base URL: {self.base_url}
    Resolution: {self.resolution}
    Bandwidth: {self.bandwidth}
    Content Length: {self.content_length} bytes"""
    
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
        }
