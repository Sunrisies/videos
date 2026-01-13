"""
M3U8下载器使用示例
展示如何以编程方式使用模块化下载器
"""

from m3u8.config import DownloadConfig, ConfigTemplates
from m3u8.downloader import M3U8Downloader
from m3u8.parser import M3U8Parser
from m3u8.utils import print_banner, FileValidator, URLProcessor


def example_basic_download():
    """基础下载示例"""
    print("=== 基础下载示例 ===")
    
    # M3U8 URL
    url = "https://europe.olemovienews.com/ts4/20260110/818a2vxr/mp4/818a2vxr.mp4/index-v1-a1.m3u8"
    
    # 创建下载器
    downloader = M3U8Downloader(url)
    
    # 执行下载
    success = downloader.download("output.mp4")
    
    if success:
        print("下载成功！")
        status = downloader.get_status()
        print(f"输出文件: {status['output_file']}")
        print(f"下载片段: {status['successful_segments']}/{status['total_segments']}")
    else:
        print("下载失败")


def example_custom_config():
    """自定义配置示例"""
    print("\n=== 自定义配置示例 ===")
    
    # 创建自定义配置
    config = DownloadConfig(
        num_threads=8,
        max_retries=5,
        retry_delay=2.0,
        connect_timeout=15,
        read_timeout=60,
        show_progress=True,
        enable_logging=True,
    )
    
    # 更新请求头
    config.update_headers({
        'Referer': 'https://example.com/',
        'X-Custom-Header': 'custom-value'
    })
    
    url = "https://europe.olemovienews.com/ts4/20260110/818a2vxr/mp4/818a2vxr.mp4/index-v1-a1.m3u8"
    
    downloader = M3U8Downloader(url, config)
    success = downloader.download("custom_output.mp4")
    
    if success:
        print("自定义配置下载成功！")


def example_using_templates():
    """使用配置模板示例"""
    print("\n=== 使用配置模板示例 ===")
    
    # 使用快速模板
    fast_config = ConfigTemplates.fast()
    print(f"快速配置: {fast_config.num_threads} 线程")
    
    # 使用稳定模板
    stable_config = ConfigTemplates.stable()
    print(f"稳定配置: {stable_config.num_threads} 线程, {stable_config.max_retries} 重试")
    
    # 使用低带宽模板
    low_config = ConfigTemplates.low_bandwidth()
    print(f"低带宽配置: {low_config.num_threads} 线程, {low_config.chunk_size} 块大小")


def example_parser_only():
    """仅解析M3U8示例"""
    print("\n=== 仅解析M3U8示例 ===")
    
    url = "https://europe.olemovienews.com/ts4/20260110/818a2vxr/mp4/818a2vxr.mp4/index-v1-a1.m3u8"
    
    parser = M3U8Parser(verify_ssl=False)
    
    try:
        ts_files, info = parser.parse_m3u8(url)
        
        print(f"解析成功！")
        print(f"TS文件数量: {len(ts_files)}")
        print(f"分辨率: {info.get('resolution', 'N/A')}")
        print(f"带宽: {info.get('bandwidth', 'N/A')}")
        print(f"基础URL: {info.get('base_url', 'N/A')}")
        
        # 显示前5个文件
        print("\n前5个TS文件:")
        for i, ts_file in enumerate(ts_files[:5], 1):
            print(f"  {i}. {ts_file}")
            
    except Exception as e:
        print(f"解析失败: {e}")


def example_validation():
    """URL验证示例"""
    print("\n=== URL验证示例 ===")
    
    test_urls = [
        "https://example.com/video.m3u8",
        "http://test.com/playlist.m3u8",
        "invalid-url",
        "ftp://example.com/video.m3u8",
        "https://europe.olemovienews.com/ts4/20260110/818a2vxr/mp4/818a2vxr.mp4/index-v1-a1.m3u8"
    ]
    
    for url in test_urls:
        is_valid = FileValidator.validate_url(url)
        normalized = URLProcessor.normalize_url(url)
        print(f"URL: {url}")
        print(f"  有效: {is_valid}")
        print(f"  标准化: {normalized}")
        print()


def example_error_handling():
    """错误处理示例"""
    print("\n=== 错误处理示例 ===")
    
    # 测试无效URL
    try:
        config = ConfigTemplates.stable()
        downloader = M3U8Downloader("invalid-url", config)
        downloader.download("test.mp4")
    except Exception as e:
        print(f"捕获到错误: {e}")
    
    # 测试不存在的URL
    try:
        config = ConfigTemplates.stable()
        config.max_retries = 1  # 减少重试次数
        downloader = M3U8Downloader("https://invalid-domain-12345.com/video.m3u8", config)
        downloader.download("test.mp4")
    except Exception as e:
        print(f"捕获到网络错误: {e}")


def main():
    """主函数"""
    print_banner()
    
    print("M3U8 Downloader Pro - 使用示例")
    print("=" * 50)
    
    # 运行各种示例
    example_basic_download()
    example_custom_config()
    example_using_templates()
    example_parser_only()
    example_validation()
    example_error_handling()
    
    print("\n" + "=" * 50)
    print("所有示例执行完成！")
    print("\n提示:")
    print("1. 在实际使用中，请确保URL有效且可访问")
    print("2. 根据网络环境调整线程数和超时设置")
    print("3. 使用配置模板可以快速设置合适的参数")
    print("4. 详细的日志会保存在 download.log 文件中")


if __name__ == '__main__':
    main()
