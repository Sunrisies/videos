from typing import Dict, Optional

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
