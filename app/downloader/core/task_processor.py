"""
任务处理器模块
处理批量任务下载逻辑
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from .config import DownloadConfig
from .download import DownloadTask
from .parser import M3U8Parser
from .progress import MultiTaskProgress, SegmentProgressTracker, TaskStatus
from .utils import extract_filename, check_ts_header


class TaskProcessor:
    """任务处理器 - 专门处理批量任务下载逻辑"""

    def __init__(self, config: DownloadConfig, download_handler, merge_handler, crypto_helper, logger=None):
        self.config = config
        self.download_handler = download_handler
        self.merge_handler = merge_handler
        self.crypto_helper = crypto_helper
        self.logger = logger  # 添加logger属性
        self._total_progress = 0
        self._total_tasks = 0  # 这将在处理任务时被更新
        self._media_sequence = 0

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
            filename = extract_filename(url)
            filepath = os.path.join(save_dir, filename)
            if os.path.exists(filepath):
                # 如果启用验证，检查文件是否有效
                if validate:
                    if check_ts_header(filepath):
                        downloaded.add(url)
                else:
                    downloaded.add(url)
        return downloaded

    def _build_encryption_info(self, parse_info: Dict, task: DownloadTask):
        """
        根据 M3U8 解析结果，构造当前任务专用的加密信息对象
        返回 None 表示无加密
        """
        if not self.config.auto_decrypt:
            return None

        if not self.crypto_helper.is_crypto_available():
            print("⚠️ 加密库未安装，无法解密。请运行: pip install pycryptodome")
            return None

        try:
            from .crypto import EncryptionInfo
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

            # 预加载密钥
            if enc_info.is_encrypted() and enc_info.uri and self.download_handler._decryptor:
                ok = self.download_handler._decryptor.load_key_from_uri(
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
        except ImportError as e:
            print(f"❌ 加密模块导入失败: {e}")
            return None
        except Exception as e:
            print(f"❌ 构建加密信息失败: {e}")
            return None

    def _download_task_with_progress(self, task: DownloadTask, progress_manager: MultiTaskProgress, total_tasks: int = 0) -> bool:
        """
        带进度条的任务下载（用于批量下载模式）

        Args:
            task: 下载任务
            progress_manager: 进度管理器
            total_tasks: 总任务数

        Returns:
            bool: 是否成功
        """
        # 添加调试信息
        print(f"🔍 开始处理任务: {task.name}")
        if progress_manager is None:
            print(f"❌ 任务 {task.name}: progress_manager 为 None")
        else:
            print(f"✅ 任务 {task.name}: progress_manager 存在")
        
        # 为当前任务创建临时子目录
        task_temp_dir = os.path.join(self.config.temp_dir, task.name)
        tracker: Optional[SegmentProgressTracker] = None
        self._total_tasks = total_tasks  # 更新总任务数
        self._total_progress += 1

        if self.download_handler.logger:
            self.download_handler.logger.info(f"任务 {self._total_progress}/{self._total_tasks} 开始处理")

        # 首先确保任务被注册到进度管理器，即使后续步骤失败
        registration_success = False
        print(f"📊 任务 {task.name}: progress_manager 类型: {type(progress_manager)}, 布尔值: {bool(progress_manager)}")
        if progress_manager:
            try:
                print(f"📊 任务 {task.name}: 尝试注册到进度管理器")
                # 先注册任务，但总数暂时为0，稍后更新
                progress_manager.register_task(task.name, 0)  # 先注册，总数为0
                print(f"✅ 任务 {task.name}: 成功注册到进度管理器")
                registration_success = True
            except Exception as e:
                print(f"❌ 任务 {task.name} 进度管理器注册失败: {e}")
                if self.download_handler.logger:
                    self.download_handler.logger.error(f"任务 {task.name} 注册进度管理器失败: {e}")
        else:
            print(f"❌ 任务 {task.name}: progress_manager 为 False")

        # 初始化跟踪器（只有在注册成功时才创建）
        if registration_success and progress_manager:
            try:
                tracker = SegmentProgressTracker(
                    task.name, 0, progress_manager)
                tracker.start_download()  # 开始下载阶段
                print(f"✅ 任务 {task.name}: 进度跟踪器创建成功")
            except Exception as e:
                print(f"❌ 任务 {task.name} 进度跟踪器创建失败: {e}")
                if self.download_handler.logger:
                    self.download_handler.logger.error(f"任务 {task.name} 创建进度跟踪器失败: {e}")
                # 即使跟踪器创建失败，任务仍已在进度管理器中注册

        try:
            # 解析M3U8
            print(f"🔍 任务 {task.name}: 开始解析M3U8: {task.url[:50]}...")
            parser = M3U8Parser(verify_ssl=self.config.verify_ssl)
            ts_files, parse_info = parser.parse_m3u8(
                task.url, self.config.headers)

            print(f"🔍 任务 {task.name}: 解析完成，共 {len(ts_files)} 个文件")

            if not ts_files:
                # 解析失败，标记任务失败
                print(f"❌ 任务 {task.name}: M3U8解析失败或无文件")
                if tracker:
                    tracker.finish(success=False, message="M3U8解析失败")
                return False
            total_segments = len(ts_files)

            # 更新任务总数 - 这是关键修复点
            if tracker:
                tracker.update_total_segments(total_segments)
                print(f"📊 任务 {task.name}: 更新总片段数为 {total_segments}")

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
                print(f"🔍 任务 {task.name}: 检测到 {len(downloaded)} 个已下载文件")

            # 下载未完成的文件（使用线程池并发下载）
            remaining_urls = [url for url in ts_files if url not in downloaded]
            if self.download_handler.logger:
                self.download_handler.logger.info(f"  [{task.name}] 剩余未下载的文件: {len(remaining_urls)}")
            print(f"🔍 任务 {task.name}: 需要下载 {len(remaining_urls)} 个文件")
            
            if len(remaining_urls) == 0:
                print(f"✅ 任务 {task.name}: 所有文件已存在，开始合并")
                if self.download_handler.logger:
                    self.download_handler.logger.info(f"任务 {task.name} 已完成,开始合并")
                os.makedirs(task.output_dir, exist_ok=True)
                output_file = os.path.join(task.output_dir, f"{task.name}.mp4")

                # 开始合并阶段
                if tracker:
                    tracker.start_merge()
                    print(f"🔧 任务 {task.name}: 开始合并文件")

                # 直接合并
                merge_success = self.merge_handler.merge_files(ts_files, output_file, task_temp_dir)
                if tracker:
                    tracker.on_merge_complete(success=merge_success, message="合并完成" if merge_success else "合并失败")
                print(f"🏁 任务 {task.name}: 合并{'成功' if merge_success else '失败'}")
                return merge_success

            # 建立 URL -> 原始索引 的映射，确保segment_index正确
            url_to_index_map = {url: i for i, url in enumerate(ts_files)}

            # 使用线程池并发下载
            print(f"🚀 任务 {task.name}: 开始下载 {len(remaining_urls)} 个文件")
            with ThreadPoolExecutor(max_workers=self.config.num_threads) as executor:
                # 创建下载任务
                futures = {}
                for url in remaining_urls:
                    filename = extract_filename(url)
                    # 从映射表中获取真实的索引，确保解密时使用正确的segment_index
                    segment_index = url_to_index_map.get(url, -1)
                    if segment_index == -1:
                        if self.download_handler.logger:
                            self.download_handler.logger.warning(f"无法找到URL的索引: {url}")
                        continue

                    future = executor.submit(
                        self.download_handler.download_file_stream,
                        url, task_temp_dir, filename, task.name, segment_index, enc_info
                    )
                    futures[future] = url

                # 等待所有任务完成
                completed_count = 0
                for future in as_completed(futures):
                    url = futures[future]
                    filename = extract_filename(url)
                    try:
                        if self.download_handler.logger:
                            self.download_handler.logger.info(f"任务 {task.name} 下载完成: {url}")
                        success = future.result()
                        if tracker:
                            tracker.on_segment_complete(
                                success=success, filename=filename)
                        if success:
                            completed_count += 1
                    except Exception as e:
                        if tracker:
                            tracker.on_segment_complete(
                                success=False, filename=filename)
                        if self.download_handler.logger:
                            self.download_handler.logger.error(f"下载片段 {url} 失败: {e}")
                        print(f"❌ 任务 {task.name}: 下载片段 {filename} 失败: {e}")

                    # 更新进度显示
                    completed = len([f for f in futures if f.done()])
                    total_remaining = len(remaining_urls)
                    if completed % 10 == 0 or completed == total_remaining:
                        downloaded_now = self.get_downloaded_files(task_temp_dir, ts_files)
                        downloaded_count = len(downloaded_now)
                        missing_count = len(ts_files) - downloaded_count
                        print(
                            f"  [{task.name}] 进度: {downloaded_count}/{len(ts_files)} 已下载, {missing_count} 剩余")

                print(f"✅ 任务 {task.name}: 所有下载任务完成，成功 {completed_count}/{len(remaining_urls)}")

                # 所有下载任务完成后，检查并合并文件
                all_downloaded = self.get_downloaded_files(
                    task_temp_dir, ts_files, validate=True)
                missing_count = len(ts_files) - len(all_downloaded)
                os.makedirs(task.output_dir, exist_ok=True)
                output_file = os.path.join(task.output_dir, f"{task.name}.mp4")

                if missing_count > 0:
                    print(f"⚠️  任务 {task.name}: 有 {missing_count} 个文件未成功下载或无效，尝试重新下载...")
                    if self.download_handler.logger:
                        self.download_handler.logger.warning(f"任务 {task.name}: {missing_count} 个文件缺失，开始重试下载")

                    # 重试下载未完成的文件（最多重试3次）
                    remaining_urls = [
                        url for url in ts_files if url not in all_downloaded]
                    max_retry_attempts = 3

                    for retry_attempt in range(max_retry_attempts):
                        retry_success_count = 0
                        for url in remaining_urls[:]:  # 使用切片复制，避免迭代时修改
                            filename = extract_filename(url)
                            segment_index = ts_files.index(url)  # 保持原始顺序
                            download_success = self.download_handler.download_file_stream(
                                url, task_temp_dir, filename, task.name, segment_index, enc_info
                            )
                            if download_success:
                                all_downloaded.add(url)
                                remaining_urls.remove(url)
                                retry_success_count += 1

                        if not remaining_urls:
                            print(f"✅ 任务 {task.name}: 重试下载成功完成")
                            break  # 所有文件都下载成功了

                        if retry_attempt < max_retry_attempts - 1:
                            print(
                                f"🔄 任务 {task.name}: 重试 {retry_attempt + 1}/{max_retry_attempts}: 成功 {retry_success_count} 个，剩余 {len(remaining_urls)} 个")

                    # 最终检查：如果还有文件缺失或无效，不允许合并
                    all_downloaded = self.get_downloaded_files(task_temp_dir, ts_files, validate=True)
                    missing_count = len(ts_files) - len(all_downloaded)

                    if missing_count > 0:
                        print(f"❌ 任务 {task.name}: {missing_count} 个文件下载失败或无效，无法合并")
                        if tracker:
                            tracker.finish(success=False, message=f"{missing_count} 个文件下载失败或无效")
                        if self.download_handler.logger:
                            self.download_handler.logger.error(
                                f"任务 {task.name}: {missing_count} 个文件下载失败或无效，无法合并")
                        return False

                # 验证所有文件的有效性
                invalid_files = []
                for url in ts_files:
                    filename = extract_filename(url)
                    filepath = os.path.join(task_temp_dir, filename)
                    if not os.path.exists(filepath):
                        invalid_files.append(filename)
                    elif not check_ts_header(filepath):
                        invalid_files.append(filename)
                        if self.download_handler.logger:
                            self.download_handler.logger.warning(f"文件 {filename} 不是有效的TS格式")

                if invalid_files:
                    print(f"❌ 任务 {task.name}: 发现 {len(invalid_files)} 个无效文件")
                    if tracker:
                        tracker.finish(success=False, message=f"{len(invalid_files)} 个无效文件")
                    if self.download_handler.logger:
                        self.download_handler.logger.error(f"任务 {task.name}: 无效文件列表: {invalid_files[:10]}")
                    return False

                # 开始合并阶段
                if tracker:
                    tracker.start_merge()
                    print(f"🔧 任务 {task.name}: 开始合并文件")

                # 执行合并
                merge_success = self.merge_handler.merge_files(ts_files, output_file, task_temp_dir)
                if tracker:
                    tracker.on_merge_complete(success=merge_success, message="合并完成" if merge_success else "合并失败")
                print(f"🏁 任务 {task.name}: 合并{'成功' if merge_success else '失败'}")
                return merge_success
        except Exception as e:
            print(f"💥 任务 {task.name} 执行异常: {e}")
            if self.download_handler.logger:
                self.download_handler.logger.warning(f"下载失败: {e}")
            if tracker:
                tracker.finish(success=False, message=f"异常: {str(e)}")
            return False