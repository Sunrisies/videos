"""
合并处理器模块
处理文件合并逻辑
"""

import os
import subprocess
from typing import List
from tqdm import tqdm
from .config import DownloadConfig
from .utils import check_ts_header


class MergeHandler:
    """合并处理器 - 专门处理文件合并逻辑"""

    def __init__(self, config: DownloadConfig, logger=None):
        self.config = config
        self.logger = logger

    def _extract_filename(self, url: str) -> str:
        """从URL提取文件名"""
        return os.path.basename(url.split('?')[0])

    def _safe_print(self, message: str, quiet_mode=False):
        """安全的打印函数"""
        if not quiet_mode:
            print(message)

    def merge_files(self, file_list: List[str], output_file: str, temp_dir: str, quiet_mode=True) -> bool:
        """使用FFmpeg合并TS文件为MP4

        Args:
            file_list: TS文件URL列表
            output_file: 输出文件路径
            temp_dir: 临时目录路径
            quiet_mode: 静默模式

        Returns:
            bool: 是否成功
        """
        # 首先验证所有文件都已下载并完整
        all_files_exist = True
        for url in file_list:
            filename = self._extract_filename(url)
            filepath = os.path.join(temp_dir, filename)
            if not os.path.exists(filepath):
                self._safe_print(f"❌ 缺失文件: {filepath}", quiet_mode)
                if self.logger:
                    self.logger.error(f"缺失文件: {filepath}")
                all_files_exist = False
            else:
                # 验证文件是否有效TS格式
                if not check_ts_header(filepath):
                    self._safe_print(f"❌ 无效文件: {filepath}", quiet_mode)
                    if self.logger:
                        self.logger.error(f"无效文件: {filepath}")
                    all_files_exist = False

        if not all_files_exist:
            self._safe_print(f"❌ 无法合并 - 存在缺失或无效的TS文件", quiet_mode)
            if self.logger:
                self.logger.error(f"无法合并 - 存在缺失或无效的TS文件")
            return False

        if self.logger:
            self.logger.info(
                f"合并文件: {output_file},temp_dir: {temp_dir}")

        # 保持M3U8中的原始顺序，不排序（确保视频片段按正确顺序合并）
        preserved_order_files = file_list

        # 创建文件列表文件用于FFmpeg
        task_name = os.path.basename(output_file).replace('.mp4', '')
        list_file = os.path.join(temp_dir, f'{task_name}_file_list.txt')

        with open(list_file, 'w', encoding='utf-8') as f:
            for url in preserved_order_files:
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
            self._safe_print("⚠️ FFmpeg未安装，使用二进制合并（可能不兼容某些视频）", quiet_mode)
            return self.merge_files_binary(preserved_order_files, output_file, temp_dir, quiet_mode)

        # 显示合并进度
        if self.config.show_progress and not quiet_mode:
            self._safe_print("🔄 使用FFmpeg合并文件...", quiet_mode)

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
            self.logger.info(f"运行FFmpeg命令: {' '.join(cmd)}")
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
            for url in file_list:
                filename = self._extract_filename(url)
                filepath = os.path.join(temp_dir, filename)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception as e:
                        if self.logger:
                            self.logger.warning(f"删除临时文件 {filename} 失败: {e}")
            # 删除目录
            if os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"删除临时目录 {temp_dir} 失败: {e}")
            if self.config.show_progress and not quiet_mode:
                self._safe_print("✅ 文件合并完成", quiet_mode)

            return True

        except subprocess.CalledProcessError as e:
            if self.logger:
                self.logger.error(
                    f"FFmpeg合并失败: {e.stderr.decode() if e.stderr else str(e)}")
            self._safe_print("⚠️ FFmpeg合并失败，尝试二进制合并...", quiet_mode)
            return self.merge_files_binary(preserved_order_files, output_file, temp_dir, quiet_mode)

    def merge_files_binary(self, file_list: List[str], output_file: str, temp_dir: str, quiet_mode=True) -> bool:
        """二进制合并TS文件（FFmpeg不可用时的回退方案）
        保持M3U8中的原始顺序

        Args:
            file_list: TS文件URL列表（已按M3U8顺序排列）
            output_file: 输出文件路径
            temp_dir: 临时目录路径
            quiet_mode: 静默模式

        Returns:
            bool: 是否成功
        """
        try:
            # 显示合并进度
            if self.config.show_progress and not quiet_mode:
                merge_bar = tqdm(
                    total=len(file_list),
                    desc="合并进度",
                    ncols=60,
                    leave=False,
                    bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}'
                )
            else:
                merge_bar = None

            with open(output_file, 'wb') as outfile:
                for url in file_list:  # 保持M3U8中的原始顺序

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

                            if merge_bar:
                                merge_bar.update(1)

                        except Exception as e:
                            if self.logger:
                                self.logger.warning(
                                    f"合并文件 {filename} 时出错: {e}")
                            continue

            if merge_bar:
                merge_bar.close()

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"二进制合并文件失败: {e}")
            return False