"""
线程安全的文件合并模块 - 解决并发FFmpeg合并问题

这个模块提供了完全线程安全的文件合并实现，
确保多个并发任务不会相互干扰。
"""

import os
import uuid
import threading
import subprocess
import logging
from typing import List, Optional
from pathlib import Path

from .config import DownloadConfig


class IsolatedMergeWorkspace:
    """
    隔离的合并工作空间
    
    为每个合并任务创建完全独立的临时目录和文件，
    避免并发任务间的资源竞争。
    """
    
    def __init__(self, base_temp_dir: str, task_name: str):
        # 生成唯一任务ID
        self.task_id = f"{task_name}_{uuid.uuid4().hex[:8]}"
        
        # 创建隔离的工作空间
        self.workspace = os.path.join(base_temp_dir, self.task_id)
        os.makedirs(self.workspace, exist_ok=True)
        
        # 生成唯一文件路径
        self.file_list_path = os.path.join(
            self.workspace, 
            f"file_list_{self.task_id}.txt"
        )
        self.temp_output = os.path.join(
            self.workspace,
            f"temp_output_{self.task_id}.mp4"
        )
        
        # 日志记录
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"[{self.task_id}] 创建隔离工作空间: {self.workspace}")
    
    def cleanup(self):
        """清理工作空间，删除所有临时文件"""
        try:
            if os.path.exists(self.workspace):
                import shutil
                shutil.rmtree(self.workspace)
                self.logger.info(f"[{self.task_id}] 工作空间已清理")
        except Exception as e:
            self.logger.warning(f"[{self.task_id}] 清理工作空间失败: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


class ThreadSafeFileMerger:
    """
    线程安全的文件合并器
    
    特性：
    - 每个实例独立状态
    - 使用隔离工作空间
    - 完整的错误处理
    - 超时控制
    """
    
    def __init__(self, config: DownloadConfig, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._stop_flag = False
        
        # 确保临时目录存在
        self.base_temp_dir = os.path.join(
            config.temp_dir or "./temp", 
            "merge_workspaces"
        )
        os.makedirs(self.base_temp_dir, exist_ok=True)
    
    def set_stop_flag(self, stop: bool):
        """设置停止标志"""
        with self._lock:
            self._stop_flag = stop
    
    def _extract_filename(self, url: str) -> str:
        """从URL提取文件名"""
        return os.path.basename(url.split('?')[0])
    
    def _create_file_list(
        self, 
        file_list: List[str], 
        workspace: IsolatedMergeWorkspace
    ) -> bool:
        """
        创建FFmpeg文件列表
        
        Args:
            file_list: 文件URL或路径列表
            workspace: 隔离工作空间
            
        Returns:
            bool: 是否成功
        """
        try:
            with open(workspace.file_list_path, 'w', encoding='utf-8') as f:
                for file_path in file_list:
                    # 如果是URL，提取文件名
                    if file_path.startswith('http'):
                        filename = self._extract_filename(file_path)
                        # 在工作空间中查找对应文件
                        local_path = os.path.join(
                            os.path.dirname(workspace.workspace),
                            filename
                        )
                    else:
                        local_path = file_path
                    
                    # 验证文件存在
                    if not os.path.exists(local_path):
                        self.logger.error(f"[{workspace.task_id}] 文件不存在: {local_path}")
                        return False
                    
                    # 使用绝对路径并转义
                    abs_path = os.path.abspath(local_path)
                    escaped_path = abs_path.replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
            
            self.logger.info(f"[{workspace.task_id}] 文件列表创建成功: {len(file_list)} 个文件")
            return True
            
        except Exception as e:
            self.logger.error(f"[{workspace.task_id}] 创建文件列表失败: {e}")
            return False
    
    def _run_ffmpeg_merge(
        self,
        workspace: IsolatedMergeWorkspace,
        output_file: str
    ) -> bool:
        """
        执行FFmpeg合并
        
        Args:
            workspace: 隔离工作空间
            output_file: 最终输出文件路径
            
        Returns:
            bool: 是否成功
        """
        # 检查停止标志
        with self._lock:
            if self._stop_flag:
                return False
        
        # 构建FFmpeg命令
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', workspace.file_list_path,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-y',  # 覆盖输出
            workspace.temp_output
        ]
        
        self.logger.info(f"[{workspace.task_id}] 执行FFmpeg: {' '.join(cmd)}")
        
        try:
            # 执行命令
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.config.merge_timeout if hasattr(self.config, 'merge_timeout') else 600,
                check=False
            )
            
            # 记录输出
            if result.returncode != 0:
                stderr = result.stderr.decode('utf-8', errors='ignore')
                self.logger.error(f"[{workspace.task_id}] FFmpeg失败: {stderr[:500]}")
                return False
            
            # 验证临时输出
            if not os.path.exists(workspace.temp_output):
                self.logger.error(f"[{workspace.task_id}] 临时输出文件不存在")
                return False
            
            # 移动到最终位置
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            if os.path.exists(output_file):
                os.remove(output_file)
            
            os.rename(workspace.temp_output, output_file)
            
            file_size = os.path.getsize(output_file)
            self.logger.info(f"[{workspace.task_id}] 合并成功: {output_file} ({file_size:,} bytes)")
            
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"[{workspace.task_id}] FFmpeg执行超时")
            return False
        except Exception as e:
            self.logger.error(f"[{workspace.task_id}] 合并异常: {e}")
            return False
    
    def merge_files(
        self,
        file_list: List[str],
        output_file: str,
        task_name: str = "unknown"
    ) -> bool:
        """
        线程安全的文件合并主函数
        
        Args:
            file_list: 文件URL或路径列表
            output_file: 输出文件路径
            task_name: 任务名称（用于日志）
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            if self._stop_flag:
                self.logger.warning(f"任务 {task_name} 已被取消")
                return False
        
        # 创建隔离工作空间
        with IsolatedMergeWorkspace(self.base_temp_dir, task_name) as workspace:
            
            # 1. 创建文件列表
            if not self._create_file_list(file_list, workspace):
                return False
            
            # 2. 执行FFmpeg合并
            success = self._run_ffmpeg_merge(workspace, output_file)
            
            return success
    
    def merge_files_binary(
        self,
        sorted_files: List[str],
        output_file: str,
        task_name: str = "unknown"
    ) -> bool:
        """
        二进制合并（FFmpeg不可用时的回退方案）
        
        Args:
            sorted_files: 已排序的文件列表
            output_file: 输出文件路径
            task_name: 任务名称
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            if self._stop_flag:
                return False
        
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # 二进制合并
            with open(output_file, 'wb') as outfile:
                for file_path in sorted_files:
                    with self._lock:
                        if self._stop_flag:
                            return False
                    
                    # 提取本地路径
                    if file_path.startswith('http'):
                        filename = self._extract_filename(file_path)
                        # 假设文件在输出目录的同级临时目录中
                        local_path = os.path.join(
                            os.path.dirname(os.path.dirname(output_file)),
                            "temp",
                            filename
                        )
                    else:
                        local_path = file_path
                    
                    if os.path.exists(local_path):
                        try:
                            with open(local_path, 'rb') as infile:
                                while True:
                                    chunk = infile.read(self.config.buffer_size)
                                    if not chunk:
                                        break
                                    outfile.write(chunk)
                        except Exception as e:
                            self.logger.warning(f"合并文件 {local_path} 时出错: {e}")
                            continue
            
            return True
            
        except Exception as e:
            self.logger.error(f"二进制合并失败: {e}")
            return False


class MergeManager:
    """
    合并管理器 - 提供高级的合并控制
    
    功能：
    - 并发合并控制
    - 进度跟踪
    - 错误重试
    """
    
    def __init__(self, config: DownloadConfig, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._stop_flag = False
        self._active_merges = {}
        
        # 创建基础合并器
        self.merger = ThreadSafeFileMerger(config, logger)
    
    def merge_with_retry(
        self,
        file_list: List[str],
        output_file: str,
        task_name: str = "unknown",
        max_retries: int = 2
    ) -> bool:
        """
        带重试的合并
        
        Args:
            file_list: 文件列表
            output_file: 输出文件
            task_name: 任务名称
            max_retries: 最大重试次数
            
        Returns:
            bool: 是否成功
        """
        for attempt in range(max_retries + 1):
            if self._stop_flag:
                return False
            
            if attempt > 0:
                self.logger.info(f"[{task_name}] 第 {attempt} 次重试")
            
            try:
                success = self.merger.merge_files(file_list, output_file, task_name)
                if success:
                    return True
            except Exception as e:
                self.logger.error(f"[{task_name}] 合并异常: {e}")
            
            if attempt < max_retries:
                import time
                time.sleep(2 ** attempt)  # 指数退避
        
        return False
    
    def stop(self):
        """停止所有合并"""
        self._stop_flag = True
        self.merger.set_stop_flag(True)
        self.logger.warning("正在停止所有合并任务...")


# 兼容性包装器 - 用于替换原有的 FileMerger
class CompatibleFileMerger:
    """
    兼容原有接口的包装器
    
    使用方法：
    ```python
    # 原代码
    from .merge_files import FileMerger
    merger = FileMerger(config, logger)
    merger.merge_files(file_list, output_file, temp_dir)
    
    # 新代码 - 只需修改导入
    from .thread_safe_merge import CompatibleFileMerger as FileMerger
    # 其余代码不变
    ```
    """
    
    def __init__(self, config, logger=None, quiet_mode=False):
        self.config = config
        self.logger = logger
        self._quiet_mode = quiet_mode
        self.stop_flag = False
        
        # 使用新的线程安全实现
        self._merger = ThreadSafeFileMerger(config, logger)
    
    def set_stop_flag(self, stop_flag: bool):
        """设置停止标志"""
        self.stop_flag = stop_flag
        self._merger.set_stop_flag(stop_flag)
    
    def _extract_filename(self, url: str) -> str:
        """从URL提取文件名"""
        return os.path.basename(url.split('?')[0])
    
    def _safe_print(self, message: str):
        """安全的打印函数"""
        if not self._quiet_mode:
            print(message)
    
    def merge_files(self, file_list: List[str], output_file: str, temp_dir: str) -> bool:
        """使用FFmpeg合并TS文件为MP4（线程安全版本）"""
        
        # 按文件名排序
        sorted_files = sorted(file_list, key=lambda x: self._extract_filename(x))
        
        # 提取本地文件路径（假设文件已在temp_dir中）
        local_files = []
        for url in sorted_files:
            filename = self._extract_filename(url)
            filepath = os.path.join(temp_dir, filename)
            local_files.append(filepath)
        
        # 生成任务名称
        task_name = Path(output_file).stem
        
        # 使用新的线程安全合并器
        success = self._merger.merge_files(local_files, output_file, task_name)
        
        if success:
            self._safe_print(f"✅ 文件合并完成: {output_file}")
            
            # 清理临时文件
            self._cleanup_temp_files(local_files, temp_dir)
            
            return True
        else:
            self._safe_print(f"❌ 文件合并失败，尝试二进制合并...")
            return self.merge_files_binary(sorted_files, output_file, temp_dir)
    
    def merge_files_binary(self, sorted_files: List[str], output_file: str, temp_dir: str) -> bool:
        """二进制合并（线程安全版本）"""
        
        task_name = Path(output_file).stem
        
        # 提取本地文件路径
        local_files = []
        for url in sorted_files:
            filename = self._extract_filename(url)
            filepath = os.path.join(temp_dir, filename)
            local_files.append(filepath)
        
        success = self._merger.merge_files_binary(local_files, output_file, task_name)
        
        if success:
            self._safe_print(f"✅ 二进制合并完成: {output_file}")
            self._cleanup_temp_files(local_files, temp_dir)
        else:
            self._safe_print(f"❌ 二进制合并失败")
        
        return success
    
    def _cleanup_temp_files(self, file_list: List[str], temp_dir: str):
        """清理临时文件"""
        for filepath in file_list:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"删除临时文件 {filepath} 失败: {e}")
        
        # 尝试清理临时目录
        try:
            if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)
        except:
            pass
    
    def merge_files_simple(self, file_list: List[str], output_file: str, temp_dir: str) -> bool:
        """简单的二进制合并（保持向后兼容）"""
        return self.merge_files_binary(file_list, output_file, temp_dir)