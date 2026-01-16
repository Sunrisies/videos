"""
高级下载器模块
支持流式下载、JSON配置文件、多任务管理、加密M3U8解密
"""

import os

import threading
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from tqdm import tqdm

from .config import DownloadConfig
from .download import DownloadTask
from .json_loader import JSONTaskLoader
from .merge_files import FileMerger
from .parser import M3U8Parser
from .crypto import EncryptionInfo, KeyManager, AESDecryptor, CryptoHelper
from .progress import MultiTaskProgress, SegmentProgressTracker
from .utils import (
    RetryHandler, setup_logger, create_session, extract_filename_from_url,
    disable_console_logging, enable_console_logging, check_ts_header
)


class StreamDownloadManager:
    """流式下载管理器 - 支持实时进度更新、顺序下载和加密解密"""

    def __init__(self, config: DownloadConfig = None):
        self.config = config or DownloadConfig()
        # 使用 utils.py 中的 create_session 函数
        self.session = create_session(
            self.config.verify_ssl, self.config.headers)

        # 状态管理
        self.stop_flag = False
        self.lock = threading.Lock()

        # 输出控制
        self._quiet_mode = True  # 静默模式，用于并发下载时减少输出
        self._output_lock = threading.Lock()  # 输出锁，防止并发输出混乱

        # 多任务进度管理器
        self._progress_manager: Optional[MultiTaskProgress] = None
        self._segment_tracker: Optional[SegmentProgressTracker] = None

        # 日志配置
        self.logger = None
        if self.config.enable_logging:
            # 使用 utils.py 中的 setup_logger 函数
            self.logger = setup_logger(__name__)

        # 重试处理器 - 使用 utils.py 中的 RetryHandler
        self.retry_handler = RetryHandler(
            max_retries=self.config.max_retries,
            retry_delay=self.config.retry_delay
        )

        # 加密相关组件
        self._decryptor: Optional[AESDecryptor] = None
        self._media_sequence: int = 0

        # 初始化加密组件（如果启用）
        if self.config.auto_decrypt and CryptoHelper.is_crypto_available():
            key_manager = KeyManager(
                cache_dir=self.config.key_cache_dir,
                cache_ttl=self.config.key_cache_ttl
            )
            self._decryptor = AESDecryptor(key_manager)

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        self.file_merger = FileMerger(
            config=self.config,
            logger=self.logger,
            quiet_mode=self._quiet_mode
        )

    def _safe_print(self, message: str, end: str = "\n", flush: bool = False, force: bool = True):
        """
        线程安全的打印函数

        Args:
            message: 要打印的消息
            end: 结尾字符
            flush: 是否立即刷新
            force: 是否强制打印（忽略静默模式）
        """
        if self._quiet_mode and not force:
            return
        with self._output_lock:
            print(message, end=end, flush=flush)

    def _signal_handler(self, signum, frame):
        """信号处理"""
        if self.logger:
            self.logger.info("收到中断信号，正在停止下载...")
        self.stop_flag = True

    def merge_files(self, file_list: List[str], output_file: str, temp_dir: str) -> bool:
        """合并文件 - 为每个任务创建独立的FileMerger实例"""
        # 首先验证所有文件都已下载并完整
        all_files_exist = True
        for url in file_list:
            filename = os.path.basename(url.split('?')[0])
            filepath = os.path.join(temp_dir, filename)
            if not os.path.exists(filepath):
                print(f"❌ 缺失文件: {filepath}")
                if self.logger:
                    self.logger.error(f"缺失文件: {filepath}")
                all_files_exist = False
            else:
                # 验证文件是否有效TS格式
                if not check_ts_header(filepath):
                    print(f"❌ 无效文件: {filepath}")
                    if self.logger:
                        self.logger.error(f"无效文件: {filepath}")
                    all_files_exist = False

        if not all_files_exist:
            print(f"❌ 无法合并 - 存在缺失或无效的TS文件")
            if self.logger:
                self.logger.error(f"无法合并 - 存在缺失或无效的TS文件")
            return False

        if self.logger:
            self.logger.info(
                f"合并文件: {file_list} 到 {output_file},temp_dir: {temp_dir}")
        merger = FileMerger(
            config=self.config,
            logger=self.logger,
            quiet_mode=self._quiet_mode
        )
        merger.set_stop_flag(self.stop_flag)
        return merger.merge_files(file_list, output_file, temp_dir)

    def download_file_stream(self, url: str, save_path: str, filename: str, task_name: str, segment_index: int = 0,enc_info: Optional[EncryptionInfo] = None) -> bool:
        """
        下载单个文件（流式，实时更新进度）

        Args:
            url: 文件URL
            save_path: 保存路径
            filename: 文件名
            task_name: 任务名称（用于显示）
            segment_index: 片段索引（用于 IV 计算）

        Returns:
            bool: 是否成功
        """
        if self.stop_flag:
            return False

        filepath = os.path.join(save_path, filename)

        # 检查文件是否已存在
        if os.path.exists(filepath):
            print(f"✓ {task_name}: {filename} 已存在，跳过")
            return True
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

                # 分块下载（静默模式下不显示实时进度）
                for chunk in response.iter_content(chunk_size=self.config.chunk_size):
                    if self.stop_flag:
                        break

                    if chunk:
                        chunks.append(chunk)
                        downloaded_size += len(chunk)

                if self.stop_flag:
                    return False

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
                            
                            if self.logger:
                                self.logger.debug(
                                    f"从缓存读取密钥: {cache_path}, 片段索引: {segment_index}, "
                                    f"密钥长度: {len(key_content)}"
                                )
                            self.logger.info(f"🔑 从缓存读取密钥: {cache_path}, 片段索引: {segment_index},秘钥：{key_content},{task_name} ")
                            # 解密数据（如果解密失败会抛出异常）
                            data = self._decrypt_segment(key_content, data, segment_index,enc_info)
                            # 解密后立即验证数据是否有效（检查TS头部）
                            if len(data) < 4 or data[0] != 0x47:
                                print(f"解密后的数据不是有效的TS格式: 第一个字节=0x{data[0]:02X if len(data) > 0 else 0}")

                        except Exception as e:
                            error_msg = f"解密失败: {e}, segment_index={segment_index}"
                            if self.logger:
                                self.logger.error(f"{task_name}: {filename} - {error_msg}")
                            self._safe_print(f"❌ {task_name}: {filename} - {error_msg}")
                            return False
                    else:
                        error_msg = f"密钥缓存文件不存在: {cache_path}"
                        if self.logger:
                            self.logger.error(f"{task_name}: {filename} - {error_msg}")
                        self._safe_print(f"❌ {task_name}: {filename} - {error_msg}")
                        return False
                else:
                    print(f"不进行解密的文件: {task_name}: {filename}")
                # 写入文件
                with open(filepath, 'wb') as f:
                    f.write(data)

                # 验证文件是否有效TS格式（双重检查）
                if not check_ts_header(filepath):
                    # 如果文件无效，删除它
                    # try:
                    #     os.remove(filepath)
                    # except:
                    #     pass
                    
                    error_msg = f"文件不是有效的TS格式（可能解密失败）"
                    if self.logger:
                        self.logger.error(f"{task_name}: {filename} - {error_msg}")
                    self._safe_print(f"❌ {task_name}: {filename} - {error_msg}")

                    return False

                return True

            result = self.retry_handler.execute_with_retry(_download)

            if result:
                if self.logger:
                    self.logger.info(f"{task_name}: {filename} 下载成功")

            return result

        except Exception as e:
            self._safe_print(f"✗ {task_name}: {filename} 下载失败 - {e}")
            if self.logger:
                self.logger.error(f"{task_name}: {filename} 下载失败 - {e}")
            return False

    def _should_decrypt(self,enc_info:Optional[EncryptionInfo] = None) -> bool:
        """判断是否需要解密"""
        return (
            self.config.auto_decrypt and
            self._decryptor is not None and
            enc_info
        )

    def _decrypt_segment(self, key: bytes, data: bytes, segment_index: int,enc_info:Optional[EncryptionInfo] = None ) -> bytes:
        """
        解密片段数据

        Args:
            data: 加密的片段数据
            segment_index: 片段索引

        Returns:
            bytes: 解密后的数据
        """
        if not self._should_decrypt(enc_info):
            return data

        try:
            # 计算实际序列号
            sequence_number = self._media_sequence + segment_index
            custom_iv = self.config.get_custom_iv()
            if custom_iv:
                iv = custom_iv
            elif enc_info.iv is not None:
                iv = enc_info.iv
            else:
                # 没有显式IV，传递None让decrypt方法根据sequence_number生成
                iv = None

            if self.logger:
                self.logger.info(
                    f"解密片段 {segment_index}: sequence_number={sequence_number}, "
                    f"media_sequence={self._media_sequence}, "
                    f"iv={'显式' if iv else '根据序列号生成'}, "
                    f"iv_hex={iv.hex()[:16] + '...' if iv else 'None'}"
                )
            return self._decryptor.decrypt(data, key, iv=iv, sequence_number=sequence_number)

        except Exception as e:
            error_msg = f"解密失败: {e}, segment_index={segment_index}, sequence_number={sequence_number}"
            if self.logger:
                self.logger.error(error_msg)
            # 解密失败不应该返回原始数据，应该抛出异常
            raise ValueError(error_msg)


    def _build_encryption_info(self,
                               parse_info: Dict,
                               task: DownloadTask) -> Optional[EncryptionInfo]:
        """
        根据 M3U8 解析结果，构造当前任务专用的加密信息对象
        返回 None 表示无加密
        """
        if not self.config.auto_decrypt:
            return None

        if not CryptoHelper.is_crypto_available():
            self._safe_print("⚠️ 加密库未安装，无法解密。请运行: pip install pycryptodome")
            return None

        encryption_data = parse_info.get('encryption')
        if not encryption_data:
            return None

        enc_info = EncryptionInfo(
            method=encryption_data.get('method', 'NONE'),
            uri=encryption_data.get('uri'),
            iv=bytes.fromhex(encryption_data['iv']) if encryption_data.get('iv') else None,
            key_format=encryption_data.get('key_format', 'identity'),
            key_format_versions=encryption_data.get('key_format_versions', '')
        )

        # 预加载密钥（仍然用公共的 _decryptor，但 key 会按 URI 缓存，不会串）
        if enc_info.is_encrypted() and enc_info.uri and self._decryptor:
            ok = self._decryptor.load_key_from_uri(
                enc_info.uri,
                task.name,  # 用任务名做缓存空间隔离
                verify_ssl=self.config.verify_ssl,
                headers=self.config.headers
            )
            if ok:
                print(f"🔐 任务【{task.name}】已加载解密密钥")
            else:
                print(f"⚠️ 任务【{task.name}】无法加载解密密钥: {enc_info.uri}")

        return enc_info
    def download_task(self, task: DownloadTask) -> bool:
        """
        下载整个任务（M3U8文件及其TS片段）
        """
        if self.stop_flag:
            return False

        self._safe_print(f"\n{'='*60}", force=True)
        self._safe_print(f"开始任务: {task.name}", force=True)
        self._safe_print(f"URL: {task.url}", force=True)
        self._safe_print(f"输出目录: {task.output_dir}", force=True)
        self._safe_print(f"{'='*60}\n", force=True)

        # 为当前任务创建临时子目录
        task_temp_dir = os.path.join(self.config.temp_dir, task.name)

        try:
            # 解析M3U8
            parser = M3U8Parser(verify_ssl=self.config.verify_ssl)
            ts_files, parse_info = parser.parse_m3u8(
                task.url, self.config.headers)
            parse_success = False

            # 使用 RetryHandler 进行重试
            def _parse_m3u8():
                nonlocal ts_files, parse_info
                ts_files, parse_info = parser.parse_m3u8(
                    task.url, self.config.headers)
                if not ts_files:
                    raise ValueError("解析M3U8成功但未找到TS文件列表")
                return True

            try:
                self._safe_print(f"🔍 正在解析 M3U8: {task.url} ...", force=True)
                if self.logger:
                    self.logger.info(
                        f"🔍 正在解析 M3U8: {task.url} ...", force=True)

                self.retry_handler.execute_with_retry(_parse_m3u8)
                parse_success = True
            except Exception as e:
                self._safe_print(
                    f"❌ 任务 {task.name}: 解析 M3U8 失败，已达最大重试次数 - {e}", force=True)
                if self.logger:
                    self.logger.error(f"解析 M3U8 失败: {e}")

            if not parse_success:
                return False
            if not ts_files:
                self._safe_print(f"❌ 任务 {task.name}: 未找到TS文件", force=True)
                return False

            self._safe_print(f"📊 找到 {len(ts_files)} 个TS文件")
            self._safe_print(f"📺 分辨率: {parse_info.get('resolution', 'N/A')}")
            self._safe_print(f"💾 带宽: {parse_info.get('bandwidth', 'N/A')}")

            # 显示加密信息
            if parse_info.get('is_encrypted'):
                enc_info = parse_info.get('encryption', {})
                self._safe_print(f"🔐 加密方式: {enc_info.get('method', 'N/A')}")
                if self.config.auto_decrypt:
                    self._safe_print("🔓 将自动解密 TS 片段")
                else:
                    self._safe_print("⚠️ 自动解密已禁用，下载原始加密数据")
            else:
                self._safe_print("🔓 未加密")

            self._safe_print("")

            # 设置加密信息
            # self._setup_encryption(parse_info)

            # 创建临时目录
            os.makedirs(task_temp_dir, exist_ok=True)

            # 检查已下载的文件
            downloaded = self.get_downloaded_files(task_temp_dir, ts_files)
            if downloaded:
                self._safe_print(f"📦 发现 {len(downloaded)} 个已下载的文件\n")

            # 下载未完成的文件
            remaining_urls = [url for url in ts_files if url not in downloaded]

            if remaining_urls:
                total_count = len(remaining_urls)
                print(f"⬇️  开始下载 {total_count} 个文件...")
                print(f"🚀 使用 {self.config.num_threads} 个线程并发下载")

                # --- 修改开始 ---
                # 为了确保索引正确，我们需要建立 URL -> 原始索引 的映射
                # 这样无论线程怎么乱序执行，都能拿到正确的 segment_index
                url_to_index_map = {url: i for i, url in enumerate(ts_files)}
                # --- 修改结束 ---

                success_count = 0
                fail_count = 0
                completed_count = 0

                # 使用线程池并发下载
                with ThreadPoolExecutor(max_workers=self.config.num_threads) as executor:
                    futures = {}
                    for url in remaining_urls:
                        if self.stop_flag:
                            break

                        filename = self._extract_filename(url)

                        # --- 修改开始 ---
                        # 从映射表中获取真实的索引，而不是使用 enumerate(remaining_urls)
                        segment_index = url_to_index_map.get(url, -1)
                        # --- 修改结束 ---

                        future = executor.submit(
                            self.download_file_stream,
                            url, task_temp_dir, filename, task.name, segment_index
                        )
                        # 这里存 future 和 url 的映射即可，不需要存 i
                        futures[future] = url

                    # 等待所有任务完成
                    for future in as_completed(futures):
                        if self.stop_flag:
                            for f in futures:
                                f.cancel()
                            break

                        url = futures[future]
                        try:
                            success = future.result()
                            if success:
                                success_count += 1
                            else:
                                fail_count += 1
                        except Exception as e:
                            fail_count += 1
                            if self.logger:
                                self.logger.error(f"下载片段 {url} 失败: {e}")

                        completed_count += 1

                        if completed_count % 10 == 0 or completed_count == total_count:
                            remaining = total_count - completed_count
                            print(
                                f"  进度: {completed_count}/{total_count} (成功: {success_count}, 失败: {fail_count}, 剩余: {remaining})")

                # 最终统计（验证文件有效性）
                final_downloaded = self.get_downloaded_files(task_temp_dir, ts_files, validate=True)
                final_success = len(final_downloaded)
                final_missing = len(ts_files) - final_success
                
                print(f"\n📊 下载完成统计:", force=True)
                print(f"   ✅ 已下载: {final_success}/{len(ts_files)}", force=True)
                print(f"   ❌ 未下载: {final_missing}/{len(ts_files)}", force=True)
                print(f"   📈 成功率: {success_count}/{total_count} (本次下载)", force=True)

            # 合并文件前，确保所有文件都已下载完成
            if not self.stop_flag:
                self._safe_print(f"🔄 准备合并文件到: {task.output_dir}")

                # 在合并前严格检查所有文件是否都存在且有效
                all_downloaded = self.get_downloaded_files(
                    task_temp_dir, ts_files, validate=True)
                missing_count = len(ts_files) - len(all_downloaded)
                
                if missing_count > 0:
                    self._safe_print(f"⚠️  有 {missing_count} 个文件未成功下载或无效，尝试重新下载...")
                    if self.logger:
                        self.logger.warning(f"任务 {task.name}: {missing_count} 个文件缺失或无效，开始重试下载")

                    # 重试下载未完成的文件（最多重试3次）
                    remaining_urls = [
                        url for url in ts_files if url not in all_downloaded]
                    max_retry_attempts = 3
                    
                    for retry_attempt in range(max_retry_attempts):
                        if self.stop_flag:
                            break
                            
                        retry_success_count = 0
                        for url in remaining_urls[:]:  # 使用切片复制，避免迭代时修改
                            filename = self._extract_filename(url)
                            segment_index = ts_files.index(url)  # 保持原始顺序
                            download_success = self.download_file_stream(
                                url, task_temp_dir, filename, task.name, segment_index
                            )
                            if download_success:
                                all_downloaded.add(url)
                                remaining_urls.remove(url)
                                retry_success_count += 1
                        
                        if not remaining_urls:
                            break  # 所有文件都下载成功了
                        
                        if retry_attempt < max_retry_attempts - 1:
                            self._safe_print(f"  重试 {retry_attempt + 1}/{max_retry_attempts}: 成功 {retry_success_count} 个，剩余 {len(remaining_urls)} 个")
                    
                    # 最终检查：如果还有文件缺失或无效，不允许合并
                    all_downloaded = self.get_downloaded_files(task_temp_dir, ts_files, validate=True)
                    missing_count = len(ts_files) - len(all_downloaded)
                    
                    if missing_count > 0:
                        self._safe_print(f"❌ 任务 {task.name}: 仍有 {missing_count} 个文件下载失败或无效，无法合并", force=True)
                        if self.logger:
                            self.logger.error(f"任务 {task.name}: {missing_count} 个文件下载失败，无法合并")
                            # 记录缺失的文件
                            missing_urls = [url for url in ts_files if url not in all_downloaded]
                            for url in missing_urls[:10]:  # 只记录前10个
                                self.logger.error(f"  缺失文件: {self._extract_filename(url)}")
                        return False
                
                # 验证所有文件的有效性
                self._safe_print("🔍 验证所有TS文件完整性...")
                invalid_files = []
                for url in ts_files:
                    filename = self._extract_filename(url)
                    filepath = os.path.join(task_temp_dir, filename)
                    if not os.path.exists(filepath):
                        invalid_files.append(filename)
                    elif not check_ts_header(filepath):
                        invalid_files.append(filename)
                        if self.logger:
                            self.logger.warning(f"文件 {filename} 不是有效的TS格式")
                
                if invalid_files:
                    self._safe_print(f"❌ 任务 {task.name}: 发现 {len(invalid_files)} 个无效文件，无法合并", force=True)
                    if self.logger:
                        self.logger.error(f"任务 {task.name}: 无效文件列表: {invalid_files[:10]}")
                    return False

                self._safe_print("✅ 所有文件下载完成并验证通过，开始合并...")

                os.makedirs(task.output_dir, exist_ok=True)
                output_file = os.path.join(task.output_dir, f"{task.name}.mp4")
                
                # 确保按照M3U8中的原始顺序合并（ts_files已经是正确顺序）
                success = self.merge_files(
                    ts_files, output_file, task_temp_dir)

                if success:
                    self._safe_print(
                        f"✅ 任务 {task.name} 完成！输出: {output_file}", force=True)
                    return True
                else:
                    self._safe_print(f"❌ 任务 {task.name}: 合并失败", force=True)
                    return False
            else:
                self._safe_print(f"⚠️  任务 {task.name} 已中断", force=True)
                return False

        except Exception as e:
            self._safe_print(f"❌ 任务 {task.name}: 执行出错 - {e}", force=True)
            if self.logger:
                self.logger.error(f"任务 {task.name} 执行出错: {e}")
            return False

        finally:
            self._media_sequence = 0

    def download_batch_tasks(self, tasks: List[DownloadTask], max_concurrent: int = 6) -> Dict[str, bool]:
        """
        批量下载多个任务（支持可控并发，带多任务进度条）

        Args:
            tasks: 任务列表
            max_concurrent: 最大并发任务数 (默认6个)

        Returns:
            Dict[str, bool]: 每个任务的执行结果
        """
        results = {}

        print(f"\n🚀 开始批量处理 {len(tasks)} 个任务")
        print(f"📊 最大并发数: {max_concurrent}")
        print(f"{'='*60}\n")

        # 创建多任务进度管理器
        self._progress_manager = MultiTaskProgress(
            max_display_tasks=max_concurrent)
        self._quiet_mode = True  # 启用静默模式，使用进度条显示

        # 禁用控制台日志输出，避免干扰进度条
        if self.logger:
            disable_console_logging(self.logger)

        try:
            # 使用线程池执行任务，限制并发数
            with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                # 提交所有任务
                futures = {}
                for task in tasks:
                    future = executor.submit(
                        self._download_task_with_progress, task)
                    futures[future] = task.name

                # 收集结果
                for future in as_completed(futures):
                    if self.stop_flag:
                        # 取消剩余任务
                        for f in futures:
                            f.cancel()
                        break

                    task_name = futures[future]
                    try:
                        result = future.result()
                        results[task_name] = result
                    except Exception as e:
                        results[task_name] = False
                        if self.logger:
                            self.logger.error(f"任务 {task_name} 异常: {e}")

        finally:
            # 恢复非静默模式
            self._quiet_mode = True

            # 恢复控制台日志输出
            if self.logger:
                enable_console_logging(self.logger)

            # 打印汇总信息
            if self._progress_manager:
                print()  # 空行分隔进度条和汇总
                self._progress_manager.print_summary()
                self._progress_manager.clear()
                self._progress_manager = None

            # 清理密钥缓存
            if self.config.clean_key_cache and self._decryptor:
                self._decryptor.key_manager.clear_cache()
                self._cleanup_key_cache_dir()

        return results

    def _cleanup_key_cache_dir(self):
        """清理密钥缓存目录"""
        try:
            cache_dir = self.config.key_cache_dir
            if os.path.exists(cache_dir):
                import shutil
                shutil.rmtree(cache_dir)
                if self.logger:
                    self.logger.info(f"已清理密钥缓存目录: {cache_dir}")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"清理密钥缓存目录失败: {e}")

    def _download_task_with_progress(self, task: DownloadTask) -> bool:
        """
        带进度条的任务下载（用于批量下载模式）

        Args:
            task: 下载任务

        Returns:
            bool: 是否成功
        """
        if self.stop_flag:
            return False

        # 为当前任务创建临时子目录
        task_temp_dir = os.path.join(self.config.temp_dir, task.name)
        tracker: Optional[SegmentProgressTracker] = None

        try:
            # 解析M3U8
            parser = M3U8Parser(verify_ssl=self.config.verify_ssl)
            ts_files, parse_info = parser.parse_m3u8(
                task.url, self.config.headers)

            if not ts_files:
                return False
            total_segments = len(ts_files)

            # 注册任务到进度管理器
            if self._progress_manager:
                self._progress_manager.register_task(task.name, total_segments)
                tracker = SegmentProgressTracker(
                    task.name, total_segments, self._progress_manager)
                tracker.start()

            # 设置加密信息
            enc_info = self._build_encryption_info(parse_info, task)

            # 创建临时目录
            os.makedirs(task_temp_dir, exist_ok=True)

            # 检查已下载的文件
            downloaded = self.get_downloaded_files(task_temp_dir, ts_files)

            # 更新已完成的进度
            if downloaded and tracker:
                for _ in range(len(downloaded)):
                    tracker.on_segment_complete(success=True)

            # 下载未完成的文件（使用线程池并发下载）
            remaining_urls = [url for url in ts_files if url not in downloaded]
            
            # 建立 URL -> 原始索引 的映射，确保segment_index正确
            url_to_index_map = {url: i for i, url in enumerate(ts_files)}

            # 使用线程池并发下载
            with ThreadPoolExecutor(max_workers=self.config.num_threads) as executor:
                # 创建下载任务
                futures = {}
                for url in remaining_urls:
                    if self.stop_flag:
                        break

                    filename = self._extract_filename(url)
                    # 从映射表中获取真实的索引，确保解密时使用正确的segment_index
                    segment_index = url_to_index_map.get(url, -1)
                    if segment_index == -1:
                        if self.logger:
                            self.logger.warning(f"无法找到URL的索引: {url}")
                        continue

                    future = executor.submit(
                        self.download_file_stream,
                        url, task_temp_dir, filename, task.name, segment_index,enc_info
                    )
                    futures[future] = url

                # 等待所有任务完成
                for future in as_completed(futures):
                    if self.stop_flag:
                        # 取消剩余任务
                        for f in futures:
                            f.cancel()
                        break

                    url = futures[future]
                    filename = self._extract_filename(url)
                    try:
                        success = future.result()
                        if tracker:
                            tracker.on_segment_complete(
                                success=success, filename=filename)
                    except Exception as e:
                        if tracker:
                            tracker.on_segment_complete(
                                success=False, filename=filename)
                        if self.logger:
                            self.logger.error(f"下载片段 {url} 失败: {e}")
                    
                    # 更新进度显示
                    completed = len([f for f in futures if f.done()])
                    total_remaining = len(remaining_urls)
                    if completed % 10 == 0 or completed == total_remaining:
                        downloaded_now = self.get_downloaded_files(task_temp_dir, ts_files)
                        downloaded_count = len(downloaded_now)
                        missing_count = len(ts_files) - downloaded_count
                        if not self._quiet_mode:
                            print(f"  [{task.name}] 进度: {downloaded_count}/{len(ts_files)} 已下载, {missing_count} 剩余")

            # 合并文件前，确保所有文件都已下载完成
            if not self.stop_flag:
                if tracker:
                    tracker.on_merge_start()

                # 在合并前严格检查所有文件是否都存在且有效
                all_downloaded = self.get_downloaded_files(
                    task_temp_dir, ts_files, validate=True)
                missing_count = len(ts_files) - len(all_downloaded)
                
                if missing_count > 0:
                    if not self._quiet_mode:
                        print(f"⚠️  有 {missing_count} 个文件未成功下载或无效，尝试重新下载...")
                    if self.logger:
                        self.logger.warning(f"任务 {task.name}: {missing_count} 个文件缺失，开始重试下载")

                    # 重试下载未完成的文件（最多重试3次）
                    remaining_urls = [
                        url for url in ts_files if url not in all_downloaded]
                    max_retry_attempts = 3
                    
                    for retry_attempt in range(max_retry_attempts):
                        if self.stop_flag:
                            break
                            
                        retry_success_count = 0
                        for url in remaining_urls[:]:  # 使用切片复制，避免迭代时修改
                            filename = self._extract_filename(url)
                            segment_index = ts_files.index(url)  # 保持原始顺序
                            download_success = self.download_file_stream(
                                url, task_temp_dir, filename, task.name, segment_index,enc_info
                            )
                            if download_success:
                                all_downloaded.add(url)
                                remaining_urls.remove(url)
                                retry_success_count += 1
                        
                        if not remaining_urls:
                            break  # 所有文件都下载成功了
                        
                        if retry_attempt < max_retry_attempts - 1:
                            if not self._quiet_mode:
                                print(f"  重试 {retry_attempt + 1}/{max_retry_attempts}: 成功 {retry_success_count} 个，剩余 {len(remaining_urls)} 个")
                    
                    # 最终检查：如果还有文件缺失或无效，不允许合并
                    all_downloaded = self.get_downloaded_files(task_temp_dir, ts_files, validate=True)
                    missing_count = len(ts_files) - len(all_downloaded)
                    
                    if missing_count > 0:
                        if tracker:
                            tracker.finish(success=False, message=f"{missing_count} 个文件下载失败或无效")
                        if self.logger:
                            self.logger.error(f"任务 {task.name}: {missing_count} 个文件下载失败或无效，无法合并")
                        return False
                
                # 验证所有文件的有效性
                invalid_files = []
                for url in ts_files:
                    filename = self._extract_filename(url)
                    filepath = os.path.join(task_temp_dir, filename)
                    if not os.path.exists(filepath):
                        invalid_files.append(filename)
                    elif not check_ts_header(filepath):
                        invalid_files.append(filename)
                        if self.logger:
                            self.logger.warning(f"文件 {filename} 不是有效的TS格式")
                
                if invalid_files:
                    if tracker:
                        tracker.finish(success=False, message=f"{len(invalid_files)} 个无效文件")
                    if self.logger:
                        self.logger.error(f"任务 {task.name}: 无效文件列表: {invalid_files[:10]}")
                    return False

                os.makedirs(task.output_dir, exist_ok=True)
                output_file = os.path.join(task.output_dir, f"{task.name}.mp4")
                
                # 确保按照M3U8中的原始顺序合并（ts_files已经是正确顺序）
                success = self.merge_files(
                    ts_files, output_file, task_temp_dir)

                if success:
                    # self.cleanup_task_temp_dir(task_temp_dir)
                    if tracker:
                        tracker.finish(success=True)
                    return True
                else:
                    if tracker:
                        tracker.finish(success=False, message="合并失败")
                    return False
            else:
                if tracker:
                    tracker.finish(success=False, message="已中断")
                return False

        except Exception as e:
            if tracker:
                tracker.finish(success=False, message=str(e)[:20])
            if self.logger:
                self.logger.error(f"任务 {task.name} 执行出错: {e}")
            return False

        finally:
            # 清理加密状态
            self._media_sequence = 0

    def _extract_filename(self, url: str) -> str:
        """从URL提取文件名"""
        # 使用 utils.py 中的 extract_filename_from_url 函数
        return extract_filename_from_url(url)

    def get_downloaded_files(self, save_dir: str, urls: List[str], validate: bool = False) -> set:
        """
        获取已下载的文件集合
        
        Args:
            save_dir: 保存目录
            urls: URL列表
            validate: 是否验证文件有效性（检查TS头部）
        
        Returns:
            已下载的文件URL集合
        """
        downloaded = set()
        for url in urls:
            filename = self._extract_filename(url)
            filepath = os.path.join(save_dir, filename)
            if os.path.exists(filepath):
                # 如果启用验证，检查文件是否有效
                if validate:
                    if check_ts_header(filepath):
                        downloaded.add(url)
                else:
                    downloaded.add(url)
        return downloaded

    def cleanup_task_temp_dir(self, task_temp_dir: str):
        """清理任务临时目录"""
        try:
            if os.path.exists(task_temp_dir):
                # 删除所有临时文件
                for filename in os.listdir(task_temp_dir):
                    filepath = os.path.join(task_temp_dir, filename)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                # 删除目录
                os.rmdir(task_temp_dir)
        except Exception as e:
            if self.logger:
                self.logger.warning(f"清理临时目录失败: {e}")


class AdvancedM3U8Downloader:
    """高级M3U8下载器 - 支持JSON配置和流式下载"""

    def __init__(self, config: DownloadConfig = None):
        self.config = config or DownloadConfig()
        self.manager = StreamDownloadManager(self.config)
        self.task_loader = JSONTaskLoader()

    def download_from_json(self, json_file: str, base_output_dir: str, max_concurrent: int = 3) -> bool:
        """
        从JSON文件下载多个任务

        Args:
            json_file: JSON配置文件路径
            base_output_dir: 基础输出目录
            max_concurrent: 最大并发任务数

        Returns:
            bool: 是否所有任务成功
        """
        try:
            # 加载任务
            tasks = self.task_loader.load_from_file(json_file, base_output_dir)

            if not tasks:
                print("❌ JSON文件中没有任务")
                return False

            print(f"📋 加载了 {len(tasks)} 个任务")

            # 执行批量下载
            results = self.manager.download_batch_tasks(tasks, max_concurrent)

            # 检查结果
            success_count = sum(1 for v in results.values() if v)
            return success_count == len(tasks)

        except Exception as e:
            print(f"❌ 执行失败: {e}")
            if self.manager.logger:
                self.manager.logger.error(f"JSON下载执行失败: {e}")
            return False

    def download_single(self, name: str, url: str, output_dir: str, params: Optional[Dict] = None) -> bool:
        """
        下载单个任务

        Args:
            name: 任务名称
            url: M3U8 URL
            output_dir: 输出目录
            params: 额外参数

        Returns:
            bool: 是否成功
        """
        task = DownloadTask(name, url, output_dir, params)
        return self.manager.download_task(task)

    def stop(self):
        """停止所有下载"""
        self.manager.stop_flag = True
