"""
M3U8 Downloader CLI 启动脚本
"""
import sys
import os

# 添加父目录到Python路径
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from downloader.cli.cli import M3U8CLI

if __name__ == "__main__":
    cli = M3U8CLI()
    args = cli.parse_arguments()
    
    if args.interactive:
        cli.interactive_mode()
    elif args.url:
        config = cli.create_config_from_args(args)
        cli.run(args, config)
    else:
        print("错误: 请提供URL或使用 -i 进入交互模式")
        print("使用 --help 查看帮助")
