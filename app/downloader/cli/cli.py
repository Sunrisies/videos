"""
命令行接口模块
提供友好的命令行交互界面
"""

import argparse
import sys
import os
from typing import Optional

from ..core.config import DownloadConfig, ConfigTemplates
from ..core.downloader import M3U8Downloader
from ..core.utils import print_banner, safe_input, confirm_action, FileValidator, URLProcessor


class M3U8CLI:
    """M3U8命令行界面"""
    
    def __init__(self):
        self.downloader: Optional[M3U8Downloader] = None
    
    def parse_arguments(self):
        """解析命令行参数"""
        parser = argparse.ArgumentParser(
            description="M3U8 Downloader Pro - 高性能M3U8视频下载器",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
使用示例:
  python -m m3u8.cli https://example.com/video.m3u8
  python -m m3u8.cli https://example.com/video.m3u8 -o myvideo.mp4 -t 8
  python -m m3u8.cli https://example.com/video.m3u8 --profile fast
  python -m m3u8.cli https://example.com/video.m3u8 --headers "Referer=https://example.com"
            """
        )
        
        # 基本参数
        parser.add_argument('url', nargs='?', help='M3U8文件URL')
        parser.add_argument('-o', '--output', help='输出文件路径', default=None)
        parser.add_argument('-t', '--threads', type=int, help='下载线程数')
        
        # 配置参数
        parser.add_argument('--profile', choices=['fast', 'stable', 'low_bandwidth'], 
                          help='下载配置模板')
        parser.add_argument('--max-retries', type=int, help='最大重试次数')
        parser.add_argument('--retry-delay', type=float, help='重试延迟(秒)')
        parser.add_argument('--connect-timeout', type=int, help='连接超时(秒)')
        parser.add_argument('--read-timeout', type=int, help='读取超时(秒)')
        
        # 路径参数
        parser.add_argument('--temp-dir', help='临时目录路径')
        parser.add_argument('--output-dir', help='输出目录路径')
        
        # 请求头参数
        parser.add_argument('--headers', help='自定义请求头 (JSON字符串或key=value格式)')
        parser.add_argument('--user-agent', help='自定义User-Agent')
        parser.add_argument('--referer', help='设置Referer')
        
        # 功能参数
        parser.add_argument('--no-ssl-verify', action='store_true', help='禁用SSL验证')
        parser.add_argument('--no-progress', action='store_true', help='禁用进度条')
        parser.add_argument('--no-logging', action='store_true', help='禁用日志')
        parser.add_argument('--dry-run', action='store_true', help='试运行，不实际下载')
        
        # 交互参数
        parser.add_argument('-i', '--interactive', action='store_true', help='交互模式')
        
        return parser.parse_args()
    
    def create_config_from_args(self, args) -> DownloadConfig:
        """从参数创建配置"""
        # 选择配置模板
        if args.profile == 'fast':
            config = ConfigTemplates.fast()
        elif args.profile == 'stable':
            config = ConfigTemplates.stable()
        elif args.profile == 'low_bandwidth':
            config = ConfigTemplates.low_bandwidth()
        else:
            config = DownloadConfig()
        
        # 应用命令行参数
        if args.threads:
            config.num_threads = args.threads
        if args.max_retries:
            config.max_retries = args.max_retries
        if args.retry_delay:
            config.retry_delay = args.retry_delay
        if args.connect_timeout:
            config.connect_timeout = args.connect_timeout
        if args.read_timeout:
            config.read_timeout = args.read_timeout
        if args.temp_dir:
            config.temp_dir = args.temp_dir
        if args.output_dir:
            config.output_dir = args.output_dir
        if args.no_ssl_verify:
            config.verify_ssl = False
        if args.no_progress:
            config.show_progress = False
        if args.no_logging:
            config.enable_logging = False
        
        # 处理请求头
        if args.headers:
            self._parse_headers(config, args.headers)
        
        if args.user_agent:
            config.headers['User-Agent'] = args.user_agent
        
        if args.referer:
            config.headers['Referer'] = args.referer
        
        return config
    
    def _parse_headers(self, config: DownloadConfig, headers_str: str):
        """解析请求头字符串"""
        headers_str = headers_str.strip()
        
        # 尝试解析JSON
        if headers_str.startswith('{'):
            try:
                import json
                headers = json.loads(headers_str)
                config.headers.update(headers)
                return
            except:
                pass
        
        # 解析key=value格式
        headers = {}
        for part in headers_str.split(','):
            if '=' in part:
                key, value = part.split('=', 1)
                headers[key.strip()] = value.strip()
        
        config.headers.update(headers)
    
    def interactive_mode(self):
        """交互模式"""
        print_banner()
        print("欢迎使用 M3U8 Downloader Pro 交互模式\n")
        
        # 获取URL
        url = safe_input("请输入M3U8文件URL: ")
        if not url:
            print("未输入URL，退出程序")
            return False
        
        # 验证URL
        if not FileValidator.validate_url(url):
            print("URL格式无效，请检查后重试")
            return False
        
        url = URLProcessor.normalize_url(url)
        
        # 选择配置
        print("\n请选择下载配置:")
        print("1. 快速模式 (高并发)")
        print("2. 稳定模式 (推荐)")
        print("3. 低带宽模式")
        print("4. 自定义配置")
        
        choice = safe_input("选择 (1-4) [2]: ", "2")
        
        if choice == "1":
            config = ConfigTemplates.fast()
        elif choice == "2":
            config = ConfigTemplates.stable()
        elif choice == "3":
            config = ConfigTemplates.low_bandwidth()
        else:
            config = self._custom_config_interactive()
        
        # 输出文件
        output = safe_input("\n输出文件名 [output.mp4]: ", "output.mp4")
        
        # 确认开始
        print(f"\n准备下载:")
        print(f"  URL: {url}")
        print(f"  输出: {output}")
        print(f"  线程数: {config.num_threads}")
        print(f"  重试次数: {config.max_retries}")
        
        if not confirm_action("\n是否开始下载"):
            print("下载已取消")
            return False
        
        # 执行下载
        return self._do_download(url, config, output)
    
    def _custom_config_interactive(self) -> DownloadConfig:
        """自定义配置交互"""
        print("\n自定义配置:")
        
        threads = safe_input("线程数 (回车使用默认): ")
        retries = safe_input("最大重试次数 (回车使用默认): ")
        
        config = DownloadConfig()
        
        if threads.isdigit():
            config.num_threads = int(threads)
        if retries.isdigit():
            config.max_retries = int(retries)
        
        return config
    
    def _do_download(self, url: str, config: DownloadConfig, output: str) -> bool:
        """执行下载"""
        try:
            self.downloader = M3U8Downloader(url, config)
            
            # 检查URL是否为M3U8
            if not url.endswith('.m3u8'):
                print(f"\n警告: URL可能不是M3U8文件: {url}")
                if not confirm_action("是否继续"):
                    return False
            
            # 执行下载
            success = self.downloader.download(output)
            
            if success:
                print(f"\n✅ 下载成功！")
                status = self.downloader.get_status()
                if status.get('output_file'):
                    print(f"文件保存在: {os.path.abspath(status['output_file'])}")
                return True
            else:
                print(f"\n❌ 下载失败")
                return False
                
        except KeyboardInterrupt:
            print("\n\n下载被用户中断")
            if self.downloader:
                self.downloader.stop()
            return False
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            return False
    
    def run(self):
        """主运行函数"""
        args = self.parse_arguments()
        
        # 交互模式
        if args.interactive or not args.url:
            return self.interactive_mode()
        
        # 命令行模式
        print_banner()
        
        # 验证URL
        if not FileValidator.validate_url(args.url):
            print(f"❌ URL格式无效: {args.url}")
            return False
        
        url = URLProcessor.normalize_url(args.url)
        
        # 创建配置
        config = self.create_config_from_args(args)
        
        # 确定输出文件
        output = args.output
        if not output:
            # 从URL生成默认文件名
            filename = url.split('/')[-1].split('?')[0]
            if not filename.endswith('.m3u8'):
                output = f"{filename}.mp4"
            else:
                output = filename.replace('.m3u8', '.mp4')
        
        # 试运行模式
        if args.dry_run:
            print("试运行模式:")
            print(f"  URL: {url}")
            print(f"  输出: {output}")
            print(f"  配置: {config.to_dict()}")
            return True
        
        # 执行下载
        return self._do_download(url, config, output)


def main():
    """主入口"""
    cli = M3U8CLI()
    success = cli.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
