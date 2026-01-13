"""
高级下载器模块
支持流式下载、JSON配置文件、多任务管理
"""

import os
import json
import time
import threading
import signal
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Callable, Any
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import warnings
from tqdm import tqdm

from .config import DownloadConfig
from .parser import M3U8Parser


class DownloadTask:
    """下载任务类"""
    
    def __init__(self, name: str, url: str, output_dir: str, params: Optional[Dict] = None):
        self.name = name
        self.url = url
        self.output_dir = output_dir
        self.params = params or {}
        self.status = "pending"  # pending, downloading, completed, failed
        self.progress = 0
        self.message = ""
    
    def to_dict(self):
        return {
            'name': self.name,
            'url': self.url,
            'output_dir': self.output_dir,
            'params': self.params,
            'status': self.status,
            'progress': self.progress,
            'message': self.message
        }


class StreamDownloadManager:
    """流式下载管理器 - 支持实时进度更新和顺序下载"""
    
    def __init__(self, config: DownloadConfig = None):
        self.config = config or DownloadConfig()
        self.session = requests.Session()
        self.session.verify = self.config.verify_ssl
        
        if not self.config.verify_ssl:
            warnings.filterwarnings('ignore', category=InsecureRequestWarning)
        
        self.session.headers.update(self.config.headers)
        
        # 状态管理
        self.stop_flag = False
        self.lock = threading.Lock()
        
        # 日志配置
        if self.config.enable_logging:
            self._setup_logging()
        
        # 重试处理器
        self.retry_handler = RetryHandler(
            max_retries=self.config.max_retries,
            retry_delay=self.config.retry_delay
        )
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self):
        """配置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('download.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _signal_handler(self, signum, frame):
        """信号处理"""
        if self.logger:
            self.logger.info("收到中断信号，正在停止下载...")
        self.stop_flag = True
    
    def download_file_stream(self, url: str, save_path: str, filename: str, task_name: str) -> bool:
        """
        下载单个文件（流式，实时更新进度）
        
        Args:
            url: 文件URL
            save_path: 保存路径
            filename: 文件名
            task_name: 任务名称（用于显示）
        
        Returns:
            bool: 是否成功
        """
        if self.stop_flag:
            return False
        
        filepath = os.path.join(save_path, filename)
        
        # 检查文件是否已存在
        if os.path.exists(filepath):
            print(f"\r✓ {task_name}: {filename} 已存在，跳过")
            return True
        
        try:
            # 显示开始下载
            print(f"\r→ 开始下载: {task_name} - {filename}", end="", flush=True)
            
            # 使用重试机制下载
            def _download():
                response = self.session.get(
                    url,
                    timeout=(self.config.connect_timeout, self.config.read_timeout),
                    stream=True
                )
                response.raise_for_status()
                
                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                
                # 分块下载，实时显示进度
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=self.config.chunk_size):
                        if self.stop_flag:
                            break
                        
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # 显示进度
                            if total_size > 0 and self.config.show_progress:
                                percent = (downloaded_size / total_size) * 100
                                print(f"\r→ {task_name}: {filename} [{percent:.1f}%] {downloaded_size}/{total_size} bytes", end="", flush=True)
                
                return not self.stop_flag
            
            result = self.retry_handler.execute_with_retry(_download)
            
            if result:
                print(f"\r✓ {task_name}: {filename} 下载完成", end="", flush=True)
                if self.logger:
                    self.logger.info(f"{task_name}: {filename} 下载成功")
            else:
                print(f"\r✗ {task_name}: {filename} 下载中断", end="", flush=True)
            
            return result
            
        except Exception as e:
            print(f"\r✗ {task_name}: {filename} 下载失败 - {e}", end="", flush=True)
            if self.logger:
                self.logger.error(f"{task_name}: {filename} 下载失败 - {e}")
            return False
    
    def download_task(self, task: DownloadTask) -> bool:
        """
        下载整个任务（M3U8文件及其TS片段）
        
        Args:
            task: 下载任务
            
        Returns:
            bool: 是否成功
        """
        if self.stop_flag:
            return False
        
        print(f"\n{'='*60}")
        print(f"开始任务: {task.name}")
        print(f"URL: {task.url}")
        print(f"输出目录: {task.output_dir}")
        print(f"{'='*60}\n")
        
        # 为当前任务创建临时子目录
        task_temp_dir = os.path.join(self.config.temp_dir, task.name)
        
        try:
            # 解析M3U8
            parser = M3U8Parser(verify_ssl=self.config.verify_ssl)
            ts_files, parse_info = parser.parse_m3u8(task.url, self.config.headers)
            
            if not ts_files:
                print(f"❌ 任务 {task.name}: 未找到TS文件")
                return False
            
            print(f"📊 找到 {len(ts_files)} 个TS文件")
            print(f"📺 分辨率: {parse_info.get('resolution', 'N/A')}")
            print(f"💾 带宽: {parse_info.get('bandwidth', 'N/A')}\n")
            
            # 创建临时目录
            os.makedirs(task_temp_dir, exist_ok=True)
            
            # 检查已下载的文件
            downloaded = self.get_downloaded_files(task_temp_dir, ts_files)
            if downloaded:
                print(f"📦 发现 {len(downloaded)} 个已下载的文件\n")
            
            # 下载未完成的文件（流式，逐个下载）
            remaining_urls = [url for url in ts_files if url not in downloaded]
            
            if remaining_urls:
                total_count = len(remaining_urls)
                print(f"⬇️  开始下载 {total_count} 个文件...\n")
                
                # 逐个下载（流式）
                success_count = 0
                fail_count = 0
                
                for i, url in enumerate(remaining_urls, 1):
                    if self.stop_flag:
                        break
                    
                    filename = self._extract_filename(url)
                    remaining = total_count - (success_count + fail_count) - 1
                    print(f"\n[{i}/{total_count}] 剩余: {remaining} ", end="")
                    
                    success = self.download_file_stream(url, task_temp_dir, filename, task.name)
                    
                    if success:
                        success_count += 1
                        # 下载成功时显示剩余数量
                        remaining_now = total_count - success_count - fail_count
                        print(f" ✅ 成功! 剩余: {remaining_now}", end="")
                    else:
                        fail_count += 1
                        remaining_now = total_count - success_count - fail_count
                        print(f" ❌ 失败! 剩余: {remaining_now}", end="")
                
                print(f"\n\n📊 下载结果: {success_count} 成功, {fail_count} 失败")
                
                if fail_count > 0 and not self.stop_flag:
                    print("⚠️  部分文件下载失败，继续合并已下载的文件...")
            else:
                print("✅ 所有文件已下载完成\n")
            
            # 合并文件
            if not self.stop_flag:
                print(f"🔄 开始合并文件到: {task.output_dir}")
                
                # 确保输出目录存在
                os.makedirs(task.output_dir, exist_ok=True)
                
                output_file = os.path.join(task.output_dir, f"{task.name}.mp4")
                success = self.merge_files(ts_files, output_file, task_temp_dir)
                
                if success:
                    print(f"✅ 任务 {task.name} 完成！输出: {output_file}")
                    
                    # 清理临时目录
                    if not self.stop_flag:
                        self.cleanup_task_temp_dir(task_temp_dir)
                        print(f"🗑️  已清理临时目录: {task_temp_dir}")
                    
                    return True
                else:
                    print(f"❌ 任务 {task.name}: 合并失败")
                    return False
            else:
                print(f"⚠️  任务 {task.name} 已中断")
                return False
                
        except Exception as e:
            print(f"❌ 任务 {task.name}: 执行出错 - {e}")
            if self.logger:
                self.logger.error(f"任务 {task.name} 执行出错: {e}")
            return False
    
    def download_batch_tasks(self, tasks: List[DownloadTask], max_concurrent: int = 6) -> Dict[str, bool]:
        """
        批量下载多个任务（支持可控并发）
        
        Args:
            tasks: 任务列表
            max_concurrent: 最大并发任务数 (默认3个)
            
        Returns:
            Dict[str, bool]: 每个任务的执行结果
        """
        results = {}
        
        print(f"\n🚀 开始批量处理 {len(tasks)} 个任务")
        print(f"📊 最大并发数: {max_concurrent}\n")
        
        # 使用线程池执行任务，限制并发数
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # 提交所有任务
            futures = {}
            for task in tasks:
                future = executor.submit(self.download_task, task)
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
        
        # 显示最终统计
        print(f"\n{'='*60}")
        print("📊 批量下载完成")
        print(f"{'='*60}")
        
        success_count = sum(1 for v in results.values() if v)
        fail_count = len(results) - success_count
        
        print(f"✅ 成功: {success_count}/{len(results)}")
        print(f"❌ 失败: {fail_count}")
        
        return results
    
    def _extract_filename(self, url: str) -> str:
        """从URL提取文件名"""
        clean_url = url.split('?')[0]
        filename = clean_url.split('/')[-1]
        if '#' in filename:
            filename = filename.split('#')[0]
        return filename
    
    def get_downloaded_files(self, save_dir: str, urls: List[str]) -> set:
        """获取已下载的文件集合"""
        downloaded = set()
        for url in urls:
            filename = self._extract_filename(url)
            filepath = os.path.join(save_dir, filename)
            if os.path.exists(filepath):
                downloaded.add(url)
        return downloaded
    
    def merge_files(self, file_list: List[str], output_file: str, temp_dir: str) -> bool:
        """合并TS文件"""
        if self.stop_flag:
            return False
        
        try:
            # 按文件名排序
            sorted_files = sorted(file_list, key=lambda x: self._extract_filename(x))
            
            # 显示合并进度
            if self.config.show_progress:
                merge_bar = tqdm(total=len(sorted_files), desc="合并进度")
            else:
                merge_bar = None
            
            with open(output_file, 'wb') as outfile:
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
                            
                            os.remove(filepath)
                            
                            if merge_bar:
                                merge_bar.update(1)
                                
                        except Exception as e:
                            if self.logger:
                                self.logger.warning(f"合并文件 {filename} 时出错: {e}")
                            continue
            
            if merge_bar:
                merge_bar.close()
            
            return not self.stop_flag
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"合并文件失败: {e}")
            return False
    
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


class JSONTaskLoader:
    """JSON任务加载器"""
    
    @staticmethod
    def load_from_file(file_path: str, base_output_dir: str) -> List[DownloadTask]:
        """
        从JSON文件加载下载任务
        
        JSON格式示例:
        [
            {
                "name": "video1",
                "url": "https://example.com/video1.m3u8",
                "output_dir": "./output/video1",
                "params": {
                    "quality": "1080p",
                    "language": "chinese"
                }
            },
            {
                "name": "video2", 
                "url": "https://example.com/video2.m3u8",
                "output_dir": "./output/video2",
                "params": {
                    "quality": "720p"
                }
            }
        ]
        
        Args:
            file_path: JSON文件路径
            base_output_dir: 基础输出目录
            
        Returns:
            List[DownloadTask]: 任务列表
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"JSON文件不存在: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        tasks = []
        for item in data:
            # 如果output_dir是相对路径，基于base_output_dir
            output_dir = item.get('output_dir', os.path.join(base_output_dir, item['name']))
            if not os.path.isabs(output_dir):
                output_dir = os.path.join(base_output_dir, output_dir)
            
            task = DownloadTask(
                name=item['name'],
                url=item['url'],
                output_dir=output_dir,
                params=item.get('params', {})
            )
            tasks.append(task)
        
        return tasks
    
    @staticmethod
    def save_to_file(tasks: List[DownloadTask], file_path: str):
        """保存任务列表到JSON文件"""
        data = [task.to_dict() for task in tasks]
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class RetryHandler:
    """重试处理器"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def execute_with_retry(self, func: Callable, *args, **kwargs):
        """执行函数，失败时重试"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                else:
                    raise last_exception
        
        raise last_exception


class AdvancedM3U8Downloader:
    """高级M3U8下载器 - 支持JSON配置和流式下载"""
    
    def __init__(self, config: DownloadConfig = None):
        self.config = config or DownloadConfig()
        self.manager = StreamDownloadManager(self.config)
        self.task_loader = JSONTaskLoader()
    
    def download_from_json(self, json_file: str, base_output_dir: str = "./output", max_concurrent: int = 3) -> bool:
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
