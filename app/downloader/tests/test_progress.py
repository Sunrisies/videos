"""
测试进度条显示功能
验证多线程下载时的进度显示是否准确
"""

import sys
import os
import time
import threading

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DownloadConfig
from downloader import DownloadManager


def simulate_download_files():
    """模拟下载多个文件来测试进度显示"""
    print("测试改进的进度显示功能")
    print("=" * 50)
    
    # 创建配置
    config = DownloadConfig()
    config.num_threads = 3  # 使用3个线程
    config.show_progress = True
    
    # 创建下载管理器
    manager = DownloadManager(config)
    
    # 模拟一些URL（使用本地文件来避免网络依赖）
    test_urls = [
        "file1.ts",
        "file2.ts", 
        "file3.ts",
        "file4.ts",
        "file5.ts"
    ]
    
    # 创建临时目录
    temp_dir = "test_temp"
    os.makedirs(temp_dir, exist_ok=True)
    
    # 创建一些模拟文件（已存在的和需要下载的）
    for i in range(3):  # 前3个文件已存在
        filepath = os.path.join(temp_dir, f"file{i+1}.ts")
        with open(filepath, 'w') as f:
            f.write(f"mock content {i+1}")
    
    print(f"准备测试:")
    print(f"- 总共 {len(test_urls)} 个文件")
    print(f"- 已存在 3 个文件")
    print(f"- 需要下载 2 个文件")
    print(f"- 使用 {config.num_threads} 个线程")
    print()
    
