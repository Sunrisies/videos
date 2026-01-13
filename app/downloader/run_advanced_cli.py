"""
M3U8 Downloader Advanced CLI 启动脚本
"""
import sys
import os

# 添加父目录到Python路径
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from downloader.cli.advanced_cli import AdvancedM3U8CLI

if __name__ == "__main__":
    cli = AdvancedM3U8CLI()
    args = cli.parse_arguments()
    cli.run(args)
