import json
from typing import List
import os
from .download import DownloadTask

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
            },
            {
                "name": "video2", 
                "url": "https://example.com/video2.m3u8",
                "output_dir": "./output/video2",
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
            output_dir = item.get('output_dir', os.path.join(
                base_output_dir, item['name']))
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

