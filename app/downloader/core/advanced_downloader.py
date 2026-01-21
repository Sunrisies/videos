"""
高级下载器模块
支持流式下载、JSON配置文件、多任务管理、加密M3U8解密
"""

import os
from typing import List, Dict, Optional, Any

from .config import DownloadConfig
from .download import DownloadTask
from .json_loader import JSONTaskLoader
from .stream_manager import StreamDownloadManager


class AdvancedM3U8Downloader:
    """高级M3U8下载器 - 支持JSON配置和流式下载"""

    def __init__(self, config: DownloadConfig = None):
        self.config = config or DownloadConfig()
        self.manager = StreamDownloadManager(self.config)
        self.task_loader = JSONTaskLoader()

    def download_single(self, name: str, url: str, output_dir: str, params: dict = None) -> Dict[str, Any]:
        """
        下载单个任务

        Args:
            name: 任务名称
            url: M3U8 URL
            output_dir: 输出目录
            params: 额外参数

        Returns:
            Dict[str, Any]: 包含下载结果和错误信息的字典
                - success: 是否成功
                - task_name: 任务名称
                - error: 错误信息（如果失败）
        """
        task = DownloadTask(name, url, output_dir, params)
        results = self.manager.download_batch_tasks([task], 1)
        success = results.get(name, False)
        
        return {
            "success": success,
            "task_name": name,
            "error": None if success else f"任务 {name} 下载失败"
        }

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
