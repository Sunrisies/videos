"""
流式下载管理器模块
主要的下载管理类，整合各组件功能
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
from .progress import MultiTaskProgress, SegmentProgressTracker, TaskStatus
from .utils import (
    setup_logger, disable_console_logging, enable_console_logging
)
from .download_handler import DownloadHandler
from .merge_handler import MergeHandler
from .task_processor import TaskProcessor


class StreamDownloadManager:
    """流式下载管理器 - 支持实时进度更新、顺序下载和加密解密"""

    def __init__(self, config: DownloadConfig = None):
        self.config = config or DownloadConfig()
        
        # 状态管理
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
            self.logger = setup_logger(__name__)

        # 当前总进度
        self._total_progress = 0
        # 一共多少个任务
        self._total_tasks = 0

        # ===== 组件初始化 =====
        self.download_handler = DownloadHandler(self.config, self.logger)
        self.merge_handler = MergeHandler(self.config, self.logger)
        
        # CryptoHelper 作为一个独立对象引用
        self.crypto_helper = self._get_crypto_helper()
        
        self.task_processor = TaskProcessor(
            self.config, 
            self.download_handler, 
            self.merge_handler,
            self.crypto_helper,
            self.logger  # 添加logger参数
        )
        
        # ===== 新增：合并专用线程池 =====
        self._merge_pool = ThreadPoolExecutor(max_workers=10)
        # 合并任务
        self._merge_task = []
        # ============================

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _get_crypto_helper(self):
        """获取加密辅助工具"""
        try:
            from .crypto import CryptoHelper
            return CryptoHelper
        except ImportError:
            class DummyCryptoHelper:
                @staticmethod
                def is_crypto_available():
                    return False
            return DummyCryptoHelper()

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
                from .utils import check_ts_header
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
                f"合并文件: {output_file},temp_dir: {temp_dir}")
        
        return self.merge_handler.merge_files(file_list, output_file, temp_dir)

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
        self._total_tasks = len(tasks)

        print(f"\n🚀 开始批量处理 {len(tasks)} 个任务")
        print(f"📊 最大并发数: {max_concurrent}")
        print(f"{'=' * 60}\n")

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
                    if self.logger:
                        self.logger.info(f"提交任务: {task.name} 到线程池")
                    # 不在控制台显示提交任务信息，避免干扰进度条
                    future = executor.submit(
                        self._download_task_with_progress, task, len(tasks))
                    futures[future] = task.name

                # 收集结果
                completed_count = 0
                failed_tasks = []  # 存储失败的任务信息
                for future in as_completed(futures):
                    task_name = futures[future]
                    try:
                        # 不显示获取任务结果的过程，避免干扰进度条
                        result = future.result()
                        if self.logger:
                            self.logger.info(f"任务 {task_name} 完成，结果: {result}")
                        results[task_name] = result
                        if result:
                            completed_count += 1
                        else:
                            failed_tasks.append(task_name)
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f"任务 {task_name} 执行异常: {e}")
                        import traceback
                        if self.logger:
                            self.logger.exception(e)
                        results[task_name] = False
                        failed_tasks.append(task_name)
                        if self.logger:
                            self.logger.error(f"任务 {task_name} 异常: {e}")

        finally:
            # 等待所有合并任务完成
            if self._merge_task:
                print(f"\n⏳ 等待合并任务完成...")
                for future in self._merge_task:
                    try:
                        merge_result = future.result()
                        if self.logger:
                            self.logger.info(f"合并任务完成: {merge_result}")
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f"合并任务异常: {e}")
                self._merge_task = []

            # 恢复非静默模式
            self._quiet_mode = False

            # 恢复控制台日志输出
            if self.logger:
                enable_console_logging(self.logger)

            # 打印汇总信息
            if self._progress_manager:
                print()  # 空行分隔进度条和汇总
                self._progress_manager.print_summary()
                
                # 打印失败任务的详细信息
                if failed_tasks:
                    print(f"\n{'='*60}")
                    print("❌ 失败任务详情")
                    print(f"{'='*60}")
                    for task_name in failed_tasks:
                        print(f"  - 任务: {task_name}")
                    print(f"{'='*60}\n")
                
                self._progress_manager.clear()
                self._progress_manager = None

            # 清理密钥缓存
            if self.config.clean_key_cache and hasattr(self.download_handler, '_decryptor') and self.download_handler._decryptor:
                self.download_handler._decryptor.key_manager.clear_cache()
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

    def _download_task_with_progress(self, task: DownloadTask, total_tasks: int = 0) -> bool:
        """
        委托给TaskProcessor处理任务下载
        """
        return self.task_processor._download_task_with_progress(task, self._progress_manager, total_tasks)