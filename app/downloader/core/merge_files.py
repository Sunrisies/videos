from typing import List, Dict, Optional
from tqdm import tqdm
import os

"""
文件合并模块 - 提供FFmpeg和二进制两种合并方式
"""

import os
import subprocess
from typing import List
from tqdm import tqdm


class FileMerger:
    """文件合并器 - 提供FFmpeg和二进制两种合并方式"""

    def __init__(self, config, logger=None, quiet_mode=False):
        """
        初始化文件合并器

        Args:
            config: 配置对象
            logger: 日志记录器
            quiet_mode: 静默模式
        """
        self.config = config
        self.logger = logger
        self._quiet_mode = quiet_mode
        self.stop_flag = False

    def set_stop_flag(self, stop_flag: bool):
        """设置停止标志"""
        self.stop_flag = stop_flag

    def _extract_filename(self, url: str) -> str:
        """从URL提取文件名"""
        # 这是一个示例，您可能需要根据实际需求修改
        return os.path.basename(url.split('?')[0])

    def _safe_print(self, message: str):
        """安全的打印函数"""
        if not self._quiet_mode:
            print(message)

    def merge_files(self, file_list: List[str], output_file: str, temp_dir: str) -> bool:
        """使用FFmpeg合并TS文件为MP4

        Args:
            file_list: TS文件URL列表
            output_file: 输出文件路径
            temp_dir: 临时目录路径

        Returns:
            bool: 是否成功
        """
        if self.stop_flag:
            return False

        try:
            # 按文件名排序
            sorted_files = sorted(
                file_list, key=lambda x: self._extract_filename(x))

            # 创建文件列表文件用于FFmpeg
            # list_file = os.path.join(temp_dir, 'file_list.txt')
            # 使用任务名称生成唯一的列表文件名
            task_name = os.path.basename(output_file).replace('.mp4', '')
            list_file = os.path.join(temp_dir, f'{task_name}_file_list.txt')

            with open(list_file, 'w', encoding='utf-8') as f:
                for url in sorted_files:
                    filename = self._extract_filename(url)
                    filepath = os.path.join(temp_dir, filename)
                    if os.path.exists(filepath):
                        # 使用绝对路径，避免路径问题
                        abs_path = os.path.abspath(filepath)
                        # FFmpeg要求路径使用单引号包裹并转义
                        f.write(f"file '{abs_path}'\n")

            # 检查FFmpeg是否可用
            try:
                subprocess.run(['ffmpeg', '-version'],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # FFmpeg不可用，回退到二进制合并
                self._safe_print("⚠️ FFmpeg未安装，使用二进制合并（可能不兼容某些视频）")
                return self.merge_files_binary(sorted_files, output_file, temp_dir)

            # 显示合并进度
            if self.config.show_progress and not self._quiet_mode:
                self._safe_print("🔄 使用FFmpeg合并文件...")

            # 使用FFmpeg合并
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',  # 处理AAC音频流
                '-y',  # 覆盖输出文件
                output_file
            ]
            if self.logger:
                    self.logger.error(f"运行FFmpeg命令: {' '.join(cmd)}")
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )

                # 清理临时文件
                if os.path.exists(list_file):
                    os.remove(list_file)

                # 清理TS文件
                for url in sorted_files:
                    filename = self._extract_filename(url)
                    filepath = os.path.join(temp_dir, filename)
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except Exception as e:
                            if self.logger:
                                self.logger.warning(f"删除临时文件 {filename} 失败: {e}")

                if self.config.show_progress and not self._quiet_mode:
                    self._safe_print("✅ 文件合并完成")

                return True

            except subprocess.CalledProcessError as e:
                if self.logger:
                    self.logger.error(f"FFmpeg合并失败: {e.stderr.decode() if e.stderr else str(e)}")
                self._safe_print("⚠️ FFmpeg合并失败，尝试二进制合并...")
                return self.merge_files_binary(sorted_files, output_file, temp_dir)

        except Exception as e:
            if self.logger:
                self.logger.error(f"合并文件失败: {e}")
            return False

    def merge_files_binary(self, sorted_files: List[str], output_file: str, temp_dir: str) -> bool:
        """二进制合并TS文件（FFmpeg不可用时的回退方案）

        Args:
            sorted_files: 已排序的TS文件URL列表
            output_file: 输出文件路径
            temp_dir: 临时目录路径

        Returns:
            bool: 是否成功
        """
        if self.stop_flag:
            return False

        try:
            # 显示合并进度
            if self.config.show_progress and not self._quiet_mode:
                merge_bar = tqdm(
                    total=len(sorted_files),
                    desc="合并进度",
                    ncols=60,
                    leave=False,
                    bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}'
                )
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
                                    chunk = infile.read(
                                        self.config.buffer_size)
                                    if not chunk:
                                        break
                                    outfile.write(chunk)

                            os.remove(filepath)

                            if merge_bar:
                                merge_bar.update(1)

                        except Exception as e:
                            if self.logger:
                                self.logger.warning(
                                    f"合并文件 {filename} 时出错: {e}")
                            continue

            if merge_bar:
                merge_bar.close()

            return not self.stop_flag

        except Exception as e:
            if self.logger:
                self.logger.error(f"二进制合并文件失败: {e}")
            return False

    def merge_files_simple(self, file_list: List[str], output_file: str, temp_dir: str) -> bool:
        """简单的二进制合并（用于StreamDownloadManager中的原始版本）

        Args:
            file_list: 文件列表
            output_file: 输出文件
            temp_dir: 临时目录

        Returns:
            bool: 是否成功
        """
        # 这个方法是原始StreamDownloadManager中使用的简单版本
        # 保持向后兼容
        sorted_files = sorted(file_list, key=lambda x: self._extract_filename(x))
        return self.merge_files_binary(sorted_files, output_file, temp_dir)