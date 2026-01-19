"""
下载处理器模块
处理单个文件的下载逻辑
"""

import os
import threading
from typing import Optional
from .crypto import EncryptionInfo
from .config import DownloadConfig
from .progress import SegmentProgressTracker
from .utils import RetryHandler, create_session, check_ts_header, extract_filename


class DownloadHandler:
    """下载处理器 - 专门处理单个文件的下载逻辑"""

    def __init__(self, config: DownloadConfig):
        self.config = config
        self.session = create_session(
            self.config.verify_ssl, self.config.headers)
        # 重试处理器
        self.retry_handler = RetryHandler(
            max_retries=self.config.max_retries,
            retry_delay=self.config.retry_delay
        )
        # 加密相关组件
        self._decryptor = None
        # 初始化加密组件（如果启用）
        if self.config.auto_decrypt and self._is_crypto_available():
            from .crypto import KeyManager, AESDecryptor
            key_manager = KeyManager(
                cache_dir=self.config.key_cache_dir,
                cache_ttl=self.config.key_cache_ttl
            )
            self._decryptor = AESDecryptor(key_manager)

    def _is_crypto_available(self):
        """检查加密库是否可用"""
        try:
            from .crypto import CryptoHelper
            return CryptoHelper.is_crypto_available()
        except ImportError:
            return False

    def _should_decrypt(self, enc_info: Optional[EncryptionInfo] = None) -> bool:
        """判断是否需要解密"""
        return (
                self.config.auto_decrypt and
                self._decryptor is not None and
                enc_info
        )

    def _decrypt_segment(self, key: bytes, data: bytes, segment_index: int,
                         enc_info: Optional[EncryptionInfo] = None) -> bytes:
        """
        解密片段数据

        Args:
            key: 解密密钥
            data: 加密的片段数据
            segment_index: 片段索引

        Returns:
            bytes: 解密后的数据
        """
        if not self._should_decrypt(enc_info):
            return data

        try:
            from .crypto import AESDecryptor
            # 计算实际序列号
            sequence_number = getattr(self, '_media_sequence', 0) + segment_index
            custom_iv = self.config.get_custom_iv()
            if custom_iv:
                iv = custom_iv
            elif enc_info.iv is not None:
                iv = enc_info.iv
            else:
                # 没有显式IV，传递None让decrypt方法根据sequence_number生成
                iv = None

            return self._decryptor.decrypt(data, key, iv=iv, sequence_number=sequence_number)

        except Exception as e:
            error_msg = f"解密失败: {e}, segment_index={segment_index}, sequence_number={sequence_number}"
            print(error_msg)
            # 解密失败不应该返回原始数据，应该抛出异常
            raise ValueError(error_msg)

    def download_file_stream(self, url: str, save_path: str, filename: str, task_name: str, segment_index: int = 0,
                             enc_info: Optional[EncryptionInfo] = None) -> bool:
        """
        下载单个文件（流式，实时更新进度）

        Args:
            url: 文件URL
            save_path: 保存路径
            filename: 文件名
            task_name: 任务名称（用于显示）
            segment_index: 片段索引（用于 IV 计算）
            enc_info: 加密信息

        Returns:
            bool: 是否成功
        """
        filepath = os.path.join(save_path, filename)

        # 检查文件是否已存在
        if os.path.exists(filepath):
            # 验证已存在的文件是否有效
            if check_ts_header(filepath):
                print(f"✓ {task_name}: {filename} 已存在，跳过")
                return True
            else:
                # 文件存在但无效，删除并重新下载
                try:
                    os.remove(filepath)
                except:
                    pass

        try:
            # 使用重试机制下载
            def _download():
                response = self.session.get(
                    url,
                    timeout=(self.config.connect_timeout,
                             self.config.read_timeout),
                    stream=True
                )
                response.raise_for_status()

                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                chunks = []

                # 分块下载
                for chunk in response.iter_content(chunk_size=self.config.chunk_size):
                    if chunk:
                        chunks.append(chunk)
                        downloaded_size += len(chunk)

                # 合并数据
                data = b''.join(chunks)

                # 如果启用解密且有加密信息，解密数据
                if self._should_decrypt(enc_info):
                    # 读取密钥缓存文件
                    cache_path = self._decryptor.key_manager.get_cache_path(task_name)

                    if os.path.exists(cache_path):
                        try:
                            # 读取密钥内容
                            with open(cache_path, 'rb') as f:
                                key_content = f.read()

                            # 解密数据（如果解密失败会抛出异常）
                            data = self._decrypt_segment(key_content, data, segment_index, enc_info)
                            # 解密后立即验证数据是否有效（检查TS头部）
                            if len(data) < 4 or data[0] != 0x47:
                                print(
                                    f"解密后的数据不是有效的TS格式: 第一个字节=0x{data[0]:02X if len(data) > 0 else 0}")

                        except Exception as e:
                            error_msg = f"解密失败: {e}, segment_index={segment_index}"
                            print(f"❌ {task_name}: {filename} - {error_msg}")
                            return False
                    else:
                        error_msg = f"密钥缓存文件不存在: {cache_path}"
                        print(f"❌ {task_name}: {filename} - {error_msg}")
                        return False
                else:
                    print(f"文件没有加密: {task_name}: {filename}")

                # 写入文件并确保数据完全写入磁盘
                with open(filepath, 'wb') as f:
                    f.write(data)
                    # 强制刷新缓冲区，确保数据写入磁盘
                    f.flush()
                    os.fsync(f.fileno())

                # 验证文件是否有效TS格式（双重检查）
                if not check_ts_header(filepath):
                    # 如果文件无效，删除它
                    try:
                        os.remove(filepath)
                    except:
                        pass

                    error_msg = f"文件不是有效的TS格式（可能解密失败）"
                    print(f"❌ {task_name}: {filename} - {error_msg}")

                    return False

                return True

            result = self.retry_handler.execute_with_retry(_download)

            if result:
                print(f"{task_name}: {filename} 下载成功")

            return result

        except Exception as e:
            print(f"✗ {task_name}: {filename} 下载失败 - {e}")
            return False