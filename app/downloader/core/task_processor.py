"""
任务处理器模块
处理批量任务下载逻辑
"""

import os
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
        if self.logger:
            self.logger.info(f"开始处理任务: {task.name}")
        # 保留开始处理任务的基本信息，这对用户了解任务进展很重要
        print(f"🔍 开始处理任务: {task.name}")
        if progress_manager is None:
            if self.logger:
                self.logger.warning(f"任务 {task.name}: progress_manager 为 None")
            else:
                print(f"❌ 任务 {task.name}: progress_manager 为 None")
        else:
            if self.logger:
                self.logger.info(f"任务 {task.name}: progress_manager 存在")
            # 保留progress_manager状态信息，这对调试很重要
            print(f"✅ 任务 {task.name}: progress_manager 存在")
        
        # 为当前任务创建临时子目录
        task_temp_dir = os.path.join(self.config.temp_dir, task.name)
        tracker: Optional[SegmentProgressTracker] = None
        self._total_tasks = total_tasks  # 更新总任务数
        self._total_progress += 1

        if self.logger:
            self.logger.info(f"任务 {self._total_progress}/{self._total_tasks} 开始处理")

        # 首先确保任务被注册到进度管理器，即使后续步骤失败
        registration_success = False
        if self.logger:
            self.logger.info(f"任务 {task.name}: progress_manager 类型: {type(progress_manager)}, 布尔值: {bool(progress_manager)}")
        # 不在控制台显示详细类型信息
        if progress_manager:
            try:
                if self.logger:
                    self.logger.info(f"任务 {task.name}: 尝试注册到进度管理器")
                # 不在控制台显示注册尝试信息
                # 先注册任务，但总数暂时为0，稍后更新
                progress_manager.register_task(task.name, 0)  # 先注册，总数为0
                if self.logger:
                    self.logger.info(f"任务 {task.name}: 成功注册到进度管理器")
                # 不在控制台显示注册成功的消息
                registration_success = True
            except Exception as e:
                if self.logger:
                    self.logger.error(f"任务 {task.name} 进度管理器注册失败: {e}")
                else:
                    print(f"❌ 任务 {task.name} 进度管理器注册失败: {e}")
                if self.logger:
                    self.logger.error(f"任务 {task.name} 注册进度管理器失败: {e}")
        else:
            if self.logger:
                self.logger.warning(f"任务 {task.name}: progress_manager 为 False")
            else:
                print(f"❌ 任务 {task.name}: progress_manager 为 False")

        # 初始化跟踪器（只有在注册成功时才创建）
        if registration_success and progress_manager:
            try:
                tracker = SegmentProgressTracker(
                    task.name, 0, progress_manager)
                tracker.start_download()  # 开始下载阶段
                if self.logger:
                    self.logger.info(f"任务 {task.name}: 进度跟踪器创建成功")
                # 不在控制台显示跟踪器创建成功的消息
            except Exception as e:
                if self.logger:
                    self.logger.error(f"任务 {task.name} 进度跟踪器创建失败: {e}")
                else:
                    print(f"❌ 任务 {task.name} 进度跟踪器创建失败: {e}")
                if self.logger:
                    self.logger.error(f"任务 {task.name} 创建进度跟踪器失败: {e}")
                # 即使跟踪器创建失败，任务仍已在进度管理器中注册

        try:
            # 解析M3U8
            if self.logger:
                self.logger.info(f"任务 {task.name}: 开始解析M3U8")
            # 保留基本的解析开始信息
            print(f"🔍 任务 {task.name}: 开始解析M3U8")
            parser = M3U8Parser(verify_ssl=self.config.verify_ssl)
            ts_files, parse_info = parser.parse_m3u8(
                task.url, self.config.headers)

            if self.logger:
                self.logger.info(f"任务 {task.name}: 解析完成，共 {len(ts_files)} 个文件")
            # 保留解析结果信息，这对用户了解任务状态很重要
            print(f"🔍 任务 {task.name}: 解析完成，共 {len(ts_files)} 个文件")

            if not ts_files:
                # 解析失败，标记任务失败
                if self.logger:
                    self.logger.error(f"任务 {task.name}: M3U8解析失败或无文件")
                else:
                    print(f"❌ 任务 {task.name}: M3U8解析失败或无文件")
                if tracker:
                    tracker.finish(success=False, message="M3U8解析失败")
                return False
            total_segments = len(ts_files)

            # 更新任务总数 - 这是关键修复点
            if tracker:
                tracker.update_total_segments(total_segments)
                if self.logger:
                    self.logger.info(f"任务 {task.name}: 更新总片段数为 {total_segments}")
                # 保留总片段数更新信息，这对用户了解任务规模很重要
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
                if self.logger:
                    self.logger.info(f"任务 {task.name}: 检测到 {len(downloaded)} 个已下载文件")

            # 下载未完成的文件（使用线程池并发下载）
            remaining_urls = [url for url in ts_files if url not in downloaded]
            if self.logger:
                self.logger.info(f"任务 {task.name}: 需要下载 {len(remaining_urls)} 个文件")
            # 保留需要下载的文件数量信息，这对用户了解任务状态很重要
            print(f"🔍 任务 {task.name}: 需要下载 {len(remaining_urls)} 个文件")
            
            if len(remaining_urls) == 0:
                if self.logger:
                    self.logger.info(f"任务 {task.name}: 所有文件已存在，开始合并")
                else:
                    print(f"✅ 任务 {task.name}: 所有文件已存在，开始合并")
                if self.logger:
                    self.logger.info(f"任务 {task.name} 已完成,开始合并")
                os.makedirs(task.output_dir, exist_ok=True)
                output_file = os.path.join(task.output_dir, f"{task.name}.mp4")

                # 开始合并阶段
                if tracker:
                    tracker.start_merge()
                    if self.logger:
                        self.logger.info(f"任务 {task.name}: 开始合并文件")

                # 直接合并
                merge_success = self.merge_handler.merge_files(ts_files, output_file, task_temp_dir)
                if tracker:
                    tracker.on_merge_complete(success=merge_success, message="合并完成" if merge_success else "合并失败")
                if self.logger:
                    self.logger.info(f"任务 {task.name}: 合并{'成功' if merge_success else '失败'}")
                else:
                    print(f"🏁 任务 {task.name}: 合并{'成功' if merge_success else '失败'}")
                return merge_success

            # 建立 URL -> 原始索引 的映射，确保segment_index正确
            url_to_index_map = {url: i for i, url in enumerate(ts_files)}

            # 使用线程池并发下载
            if self.logger:
                self.logger.info(f"任务 {task.name}: 开始下载 {len(remaining_urls)} 个文件")
            # 不在控制台显示开始下载的信息
            with ThreadPoolExecutor(max_workers=self.config.num_threads) as executor:
                # 创建下载任务
                futures = {}
                for url in remaining_urls:
                    filename = extract_filename(url)
                    # 从映射表中获取真实的索引，确保解密时使用正确的segment_index
                    segment_index = url_to_index_map.get(url, -1)
                    if segment_index == -1:
                        if self.logger:
                            self.logger.warning(f"无法找到URL的索引: {url}")
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
                        if self.logger:
                            self.logger.info(f"任务 {task.name} 下载完成: {url}")
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
                        if self.logger:
                            self.logger.error(f"下载片段 {url} 失败: {e}")

                    # 更新进度显示 - 只在日志中记录，不在控制台输出
                    completed = len([f for f in futures if f.done()])
                    total_remaining = len(remaining_urls)
                    if completed % 10 == 0 or completed == total_remaining:
                        downloaded_now = self.get_downloaded_files(task_temp_dir, ts_files)
                        downloaded_count = len(downloaded_now)
                        missing_count = len(ts_files) - downloaded_count
                        if self.logger:
                            self.logger.info(f"任务 {task.name} 进度: {downloaded_count}/{len(ts_files)} 已下载, {missing_count} 剩余")

                if self.logger:
                    self.logger.info(f"任务 {task.name}: 所有下载任务完成，成功 {completed_count}/{len(remaining_urls)}")
                # 不在控制台显示完成统计

                # 所有下载任务完成后，检查并合并文件
                all_downloaded = self.get_downloaded_files(
                    task_temp_dir, ts_files, validate=True)
                missing_count = len(ts_files) - len(all_downloaded)
                os.makedirs(task.output_dir, exist_ok=True)
                output_file = os.path.join(task.output_dir, f"{task.name}.mp4")

                if missing_count > 0:
                    if self.logger:
                        self.logger.warning(f"任务 {task.name}: 有 {missing_count} 个文件未成功下载或无效，尝试重新下载...")
                    else:
                        print(f"⚠️  任务 {task.name}: 有 {missing_count} 个文件未成功下载或无效，尝试重新下载...")
                    if self.logger:
                        self.logger.warning(f"任务 {task.name}: {missing_count} 个文件缺失，开始重试下载")

                    # 重试下载未完成的文件（最多重试3次）
                    remaining_urls = [
                        url for url in ts_files if url not in all_downloaded]
                    max_retry_attempts = 3

                    for retry_attempt in range(max_retry_attempts):
                        if self.logger:
                            self.logger.info(f"任务 {task.name}: 重试 {retry_attempt + 1}/{max_retry_attempts}")
                        # 不在控制台显示重试信息
                        retry_urls = []

                        for url in remaining_urls:
                            filename = extract_filename(url)
                            filepath = os.path.join(task_temp_dir, filename)
                            
                            # 检查文件是否存在且有效
                            if os.path.exists(filepath) and check_ts_header(filepath):
                                continue  # 文件有效，跳过
                        
                            # 重新下载文件
                            try:
                                success = self.download_handler.download_file_stream(
                                    url, task_temp_dir, filename, task.name, url_to_index_map[url], enc_info)
                                if success:
                                    if self.logger:
                                        self.logger.info(f"任务 {task.name}: 重试下载成功 {filename}")
                                else:
                                    retry_urls.append(url)  # 重试失败，加入下次重试列表
                                    if self.logger:
                                        self.logger.warning(f"任务 {task.name}: 重试下载失败 {filename}")
                            except Exception as e:
                                retry_urls.append(url)  # 出现异常，加入重试列表
                                if self.logger:
                                    self.logger.error(f"任务 {task.name}: 重试下载异常 {filename}, 错误: {e}")

                        if not retry_urls:
                            if self.logger:
                                self.logger.info(f"任务 {task.name}: 所有文件重试下载完成")
                            # 不在控制台显示重试完成信息
                            break  # 所有文件下载成功，退出重试循环
                        else:
                            if self.logger:
                                self.logger.warning(f"任务 {task.name}: 仍有 {len(retry_urls)} 个文件未成功下载")
                            # 不在控制台显示仍有文件未下载的信息
                            remaining_urls = retry_urls  # 更新重试列表

                    # 检查重试后是否仍有缺失的文件
                    all_downloaded = self.get_downloaded_files(
                        task_temp_dir, ts_files, validate=True)
                    missing_count = len(ts_files) - len(all_downloaded)
                    if missing_count > 0:
                        if self.logger:
                            self.logger.error(f"任务 {task.name}: 重试后仍有 {missing_count} 个文件未成功下载，合并失败")
                        else:
                            print(f"❌ 任务 {task.name}: 重试后仍有 {missing_count} 个文件未成功下载，合并失败")
                        if tracker:
                            tracker.finish(success=False, message=f"有 {missing_count} 个文件下载失败")
                        return False

                # 合并文件
                if self.logger:
                    self.logger.info(f"任务 {task.name}: 开始合并文件")
                # 不在控制台显示合并开始信息
                if tracker:
                    tracker.start_merge()
                
                merge_success = self.merge_handler.merge_files(ts_files, output_file, task_temp_dir)
                
                if tracker:
                    tracker.on_merge_complete(
                        success=merge_success, 
                        message="合并完成" if merge_success else f"合并失败: {missing_count} 个文件缺失"
                    )
                
                if self.logger:
                    self.logger.info(f"任务 {task.name}: 合并{'成功' if merge_success else '失败'}")
                # 不在控制台显示合并结果，让进度条显示最终状态
                return merge_success

        except Exception as e:
            if self.logger:
                self.logger.error(f"任务 {task.name} 执行异常: {e}")
                self.logger.exception(e)  # 记录完整的异常堆栈
            else:
                print(f"❌ 任务 {task.name} 执行异常: {e}")
                import traceback
                traceback.print_exc()
            if tracker:
                tracker.finish(success=False, message=str(e))
            if self.logger:
                self.logger.error(f"任务 {task.name} 执行异常: {e}")
            return False
