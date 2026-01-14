"""
下载器核心模块
包含文件下载、错误处理、重试机制等功能
"""

import os
import time
import threading
import signal
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Callable
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import warnings
from tqdm import tqdm

from .config import DownloadConfig
from .parser import M3U8Parser
from .utils import RetryHandler, setup_logger, create_session, extract_filename_from_url


class DownloadManager:
    """下载管理器"""

    def __init__(self, config: DownloadConfig = None):
        self.config = config or DownloadConfig()
        # 使用 utils.py 中的 create_session 函数
        self.session = create_session(
            self.config.verify_ssl, self.config.headers)

        # 状态管理
        self.stop_flag = False
        self.lock = threading.Lock()
        self.progress_bar = None

        # 日志配置
        if self.config.enable_logging:
            # 使用 utils.py 中的 setup_logger 函数
            self.logger = setup_logger(__name__)

        # 重试处理器 - 使用 utils.py 中的 RetryHandler
        self.retry_handler = RetryHandler(
            max_retries=self.config.max_retries,
            retry_delay=self.config.retry_delay
        )

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """信号处理"""
        if self.logger:
            self.logger.info("收到中断信号，正在停止下载...")
        self.stop_flag = True

    def download_file(self, url: str, save_path: str, filename: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        下载单个文件

        Args:
            url: 文件URL
            save_path: 保存目录
            filename: 文件名
            progress_callback: 进度更新回调函数

        Returns:
            bool: 是否下载成功
        """
        if self.stop_flag:
            return False

        filepath = os.path.join(save_path, filename)

        # 检查文件是否已存在
        if os.path.exists(filepath):
            if progress_callback:
                progress_callback()
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

                # 分块下载，避免内存溢出
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=self.config.chunk_size):
                        if chunk:
                            f.write(chunk)

                return True

            result = self.retry_handler.execute_with_retry(_download)

            # 更新进度（线程安全的方式）
            if progress_callback:
                progress_callback()

            if self.logger:
                self.logger.info(f"成功下载: {filename}")

            return result

        except Exception as e:
            if not self.stop_flag:
                if self.logger:
                    self.logger.error(f"下载失败 {url}: {e}")
                else:
                    print(f"下载失败 {url}: {e}")
            return False

    def download_batch(self, urls: List[str], save_dir: str, progress_desc: str = "下载进度") -> Dict[str, bool]:
        """
        批量下载文件 - 改进的进度显示

        Args:
            urls: URL列表
            save_dir: 保存目录
            progress_desc: 进度条描述

        Returns:
            Dict[str, bool]: 每个URL的下载结果
        """
        # 确保保存目录存在
        os.makedirs(save_dir, exist_ok=True)

        total_count = len(urls)
        results = {}

        # 下载状态跟踪
        status_lock = threading.Lock()
        completed_count = 0
        failed_count = 0
        active_downloads = set()  # 当前正在下载的文件

        def update_progress(filename: str, success: bool, is_completed: bool):
            """线程安全的进度更新"""
            nonlocal completed_count, failed_count

            with status_lock:
                if is_completed:
                    # 下载完成
                    if success:
                        completed_count += 1
                    else:
                        failed_count += 1

                    # 从活跃下载中移除
                    active_downloads.discard(filename)
                else:
                    # 开始下载
                    active_downloads.add(filename)

                # 显示当前状态
                if self.config.show_progress:
                    # 清除当前行并重新显示
                    active_count = len(active_downloads)
                    status_line = (f"\r{progress_desc}: {completed_count}/{total_count} 完成, "
                                   f"{failed_count} 失败, {active_count} 下载中...")
                    print(status_line, end="", flush=True)

        try:
            with ThreadPoolExecutor(max_workers=self.config.num_threads) as executor:
                # 提交所有下载任务
                futures = {}
                for url in urls:
                    filename = self._extract_filename(url)

                    # 检查文件是否已存在
                    filepath = os.path.join(save_dir, filename)
                    if os.path.exists(filepath):
                        results[url] = True
                        completed_count += 1
                        continue

                    # 创建带状态更新的下载函数
                    def create_download_task(url, filename):
                        def task():
                            # 通知开始下载
                            update_progress(filename, False, False)

                            try:
                                success = self.download_file(
                                    url, save_dir, filename, None)
                                update_progress(filename, success, True)
                                return success
                            except Exception as e:
                                update_progress(filename, False, True)
                                raise e

                        return task

                    future = executor.submit(
                        create_download_task(url, filename))
                    futures[future] = url

                # 收集结果
                for future in as_completed(futures):
                    if self.stop_flag:
                        # 取消剩余任务
                        for f in futures:
                            f.cancel()
                        break

                    url = futures[future]
                    try:
                        result = future.result()
                        results[url] = result
                    except Exception as e:
                        results[url] = False
                        if self.logger:
                            self.logger.error(f"任务异常 {url}: {e}")

            # 显示最终统计
            if self.config.show_progress:
                print()  # 换行
                print(
                    f"下载完成: {completed_count}/{total_count} 成功, {failed_count} 失败")

        except Exception as e:
            if self.config.show_progress:
                print()  # 换行
            raise e

        return results

    def _extract_filename(self, url: str) -> str:
        """从URL提取文件名"""
        # 使用 utils.py 中的 extract_filename_from_url 函数
        return extract_filename_from_url(url)

    def get_downloaded_files(self, save_dir: str, urls: List[str]) -> set:
        """获取已下载的文件集合"""
        downloaded = set()
        for url in urls:
            filename = self._extract_filename(url)
            filepath = os.path.join(save_dir, filename)
            if os.path.exists(filepath):
                downloaded.add(url)
        return downloaded

    # def merge_files(self, file_list: List[str], output_file: str, temp_dir: str) -> bool:
    #     """
    #     合并TS文件

    #     Args:
    #         file_list: 文件URL列表（用于排序）
    #         output_file: 输出文件路径
    #         temp_dir: 临时目录

    #     Returns:
    #         bool: 是否合并成功
    #     """
    #     if self.stop_flag:
    #         return False

    #     try:
    #         if self.logger:
    #             self.logger.info("开始合并文件...")

    #         # 按文件名排序
    #         sorted_files = sorted(
    #             file_list, key=lambda x: self._extract_filename(x))

    #         if self.config.show_progress:
    #             merge_bar = tqdm(
    #                 total=len(sorted_files),
    #                 desc="合并进度",
    #                 ncols=60,
    #                 leave=False,
    #                 bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}'
    #             )
    #         else:
    #             merge_bar = None

    #         with open(output_file, 'wb') as outfile:
    #             for url in sorted_files:
    #                 if self.stop_flag:
    #                     break

    #                 filename = self._extract_filename(url)
    #                 filepath = os.path.join(temp_dir, filename)

    #                 if os.path.exists(filepath):
    #                     try:
    #                         with open(filepath, 'rb') as infile:
    #                             # 使用缓冲区读取，避免大文件内存问题
    #                             while True:
    #                                 chunk = infile.read(
    #                                     self.config.buffer_size)
    #                                 if not chunk:
    #                                     break
    #                                 outfile.write(chunk)

    #                         # 删除已合并的临时文件
    #                         os.remove(filepath)

    #                         if merge_bar:
    #                             merge_bar.update(1)

    #                     except Exception as e:
    #                         if self.logger:
    #                             self.logger.warning(
    #                                 f"合并文件 {filename} 时出错: {e}")
    #                         continue

    #         if merge_bar:
    #             merge_bar.close()

    #         if self.logger:
    #             self.logger.info(f"文件合并完成: {output_file}")

    #         return not self.stop_flag

    #     except Exception as e:
    #         if self.logger:
    #             self.logger.error(f"合并文件失败: {e}")
    #         return False
    def merge_files(self, file_list: List[str], output_file: str, temp_dir: str) -> bool:
        """
        合并TS文件并转换为MP4

        Args:
            file_list: 文件URL列表（用于排序）
            output_file: 输出文件路径
            temp_dir: 临时目录

        Returns:
            bool: 是否合并成功
        """
        if self.stop_flag:
            return False

        try:
            if self.logger:
                self.logger.info("开始合并文件...")

            # 按文件名排序
            sorted_files = sorted(
                file_list, key=lambda x: self._extract_filename(x))

            # 创建临时合并文件
            temp_merged = os.path.join(temp_dir, "temp_merged.ts")
            
            if self.config.show_progress:
                merge_bar = tqdm(
                    total=len(sorted_files),
                    desc="合并进度",
                    ncols=60,
                    leave=False,
                    bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}'
                )
            else:
                merge_bar = None

            # 先合并所有TS文件
            with open(temp_merged, 'wb') as outfile:
                for url in sorted_files:
                    if self.stop_flag:
                        break

                    filename = self._extract_filename(url)
                    filepath = os.path.join(temp_dir, filename)

                    if os.path.exists(filepath):
                        try:
                            with open(filepath, 'rb') as infile:
                                while True:
                                    chunk = infile.read(self.config.buffer_size)
                                    if not chunk:
                                        break
                                    outfile.write(chunk)

                            # 删除已合并的临时文件
                            os.remove(filepath)

                            if merge_bar:
                                merge_bar.update(1)

                        except Exception as e:
                            if self.logger:
                                self.logger.warning(f"合并文件 {filename} 时出错: {e}")
                            continue

            if merge_bar:
                merge_bar.close()

            # 使用ffmpeg将TS转换为MP4
            if self.stop_flag:
                if os.path.exists(temp_merged):
                    os.remove(temp_merged)
                return False

            if self.logger:
                self.logger.info("开始转换为MP4格式...")

            try:
                # 使用ffmpeg进行转换
                cmd = [
                    'ffmpeg',
                    '-i', temp_merged,
                    '-c', 'copy',  # 直接复制流，不重新编码
                    '-bsf:a', 'aac_adtstoasc',  # 处理AAC音频流
                    output_file
                ]
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                
                # 等待转换完成
                _, stderr = process.communicate()
                
                if process.returncode != 0:
                    raise Exception(f"FFmpeg转换失败: {stderr}")
                
                if self.logger:
                    self.logger.info(f"文件转换完成: {output_file}")
                
                # 删除临时合并文件
                if os.path.exists(temp_merged):
                    os.remove(temp_merged)
                
                return True

            except Exception as e:
                if self.logger:
                    self.logger.error(f"转换为MP4失败: {e}")
                # 清理临时文件
                if os.path.exists(temp_merged):
                    os.remove(temp_merged)
                return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"合并文件失败: {e}")
    def cleanup_temp_dir(self, temp_dir: str):
        """清理临时目录"""
        try:
            if os.path.exists(temp_dir):
                # 删除所有临时文件
                for filename in os.listdir(temp_dir):
                    filepath = os.path.join(temp_dir, filename)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                # 删除目录
                os.rmdir(temp_dir)

                if self.logger:
                    self.logger.info("临时目录清理完成")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"清理临时目录失败: {e}")


class M3U8Downloader:
    """M3U8下载器主类"""

    def __init__(self, url: str, config: DownloadConfig = None):
        self.url = url
        self.config = config or DownloadConfig()
        self.parser = M3U8Parser(verify_ssl=self.config.verify_ssl)
        self.manager = DownloadManager(self.config)

        # 下载状态
        self.download_info = None
        self.is_downloading = False

    def download(self, output_file: str = None) -> bool:
        """
        主下载流程

        Args:
            output_file: 输出文件路径

        Returns:
            bool: 下载是否成功
        """
        if output_file is None:
            output_file = os.path.join(self.config.output_dir, "output.mp4")

        self.is_downloading = True

        try:
            # 打印系统信息
            print(f"系统CPU核心数: {self.config.num_threads // 2}")
            print(f"使用线程数: {self.config.num_threads}")
            print("按 Ctrl+C 可以停止下载")

            # 解析M3U8
            print("\n解析M3U8文件...")
            ts_files, parse_info = self.parser.parse_m3u8(
                self.url, self.config.headers)

            if not ts_files:
                print("未找到任何TS文件")
                return False

            print(f"找到 {len(ts_files)} 个TS文件")

            # 显示解析信息
            if self.manager.logger:
                self.manager.logger.info(
                    f"分辨率: {parse_info.get('resolution', 'N/A')}")
                self.manager.logger.info(
                    f"带宽: {parse_info.get('bandwidth', 'N/A')}")

            # 检查已下载的文件
            downloaded = self.manager.get_downloaded_files(
                self.config.temp_dir, ts_files)
            if downloaded:
                print(f"发现 {len(downloaded)} 个已下载的文件")

            # 下载未完成的文件
            remaining_urls = [url for url in ts_files if url not in downloaded]

            if remaining_urls:
                print(f"\n开始下载 {len(remaining_urls)} 个文件...")
                results = self.manager.download_batch(
                    remaining_urls,
                    self.config.temp_dir,
                    "下载进度"
                )

                # 检查下载结果
                failed = sum(1 for v in results.values() if not v)
                if failed > 0:
                    print(f"\n有 {failed} 个文件下载失败")
                    if not self.manager.stop_flag:
                        # 继续尝试合并已下载的文件
                        pass
                    else:
                        return False
            else:
                print("\n所有文件已下载完成")

            # 合并文件
            if not self.manager.stop_flag:
                print("\n开始合并文件...")
                success = self.manager.merge_files(
                    ts_files, output_file, self.config.temp_dir)

                if success:
                    # 清理临时文件
                    if not self.manager.stop_flag:
                        self.manager.cleanup_temp_dir(self.config.temp_dir)

                    print(f"\n下载完成！文件保存为: {output_file}")
                    self.download_info = {
                        'output_file': output_file,
                        'total_segments': len(ts_files),
                        'successful_segments': len(ts_files) - failed if 'failed' in locals() else len(ts_files),
                        'resolution': parse_info.get('resolution', 'N/A'),
                        'bandwidth': parse_info.get('bandwidth', 'N/A'),
                    }
                    return True
                else:
                    print("\n合并过程被中断")
                    return False
            else:
                print("\n下载已停止")
                return False

        except Exception as e:
            if self.manager.logger:
                self.manager.logger.error(f"下载过程出错: {e}")
            else:
                print(f"下载过程出错: {e}")
            return False

        finally:
            self.is_downloading = False

    def stop(self):
        """停止下载"""
        self.manager.stop_flag = True

    def get_status(self) -> Dict:
        """获取下载状态"""
        if self.download_info:
            return self.download_info
        return {'status': 'not_started'}
