"""
M3U8 Downloader Pro - 功能演示
展示新版本的核心功能
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def demo_json_config():
    """演示JSON配置文件创建"""
    print("=" * 60)
    print("📋 演示: JSON配置文件创建")
    print("=" * 60)
    
    import json
    
    # 示例配置
    tasks = [
        {
            "name": "demo_video1",
            "url": "https://europe.olemovienews.com/ts4/20260110/818a2vxr/mp4/818a2vxr.mp4/index-v1-a1.m3u8",
            "output_dir": "./output/demo_video1",
            "params": {
                "quality": "1080p",
                "language": "chinese",
                "category": "demo"
            }
        },
        {
            "name": "demo_video2",
            "url": "https://example.com/sample.m3u8",
            "output_dir": "./output/demo_video2",
            "params": {
                "quality": "720p",
                "language": "english",
                "category": "demo"
            }
        }
    ]
    
    print("\n示例JSON配置:")
    print(json.dumps(tasks, ensure_ascii=False, indent=2))
    
    print("\n💡 使用方法:")
    print("1. 保存为 demo_tasks.json")
    print("2. 运行: python -m m3u8.advanced_cli --json demo_tasks.json")
    
    return True


def demo_stream_progress():
    """演示流式进度显示"""
    print("\n" + "=" * 60)
    print("📊 演示: 流式进度显示")
    print("=" * 60)
    
    print("\n模拟下载过程:")
    print("-" * 40)
    
    # 模拟流式下载进度
    import time
    
    segments = 5
    for i in range(1, segments + 1):
        filename = f"seg-{i:03d}.ts"
        
        # 模拟下载进度
        for percent in [20, 40, 60, 80, 100]:
            print(f"\r→ demo_task: {filename} [{percent}%] {percent*1000}/{100000} bytes", end="", flush=True)
            time.sleep(0.05)
        
        print(f"\n✓ demo_task: {filename} 下载完成")
        
        if i < segments:
            print(f"\n[{i+1}/{segments}] ", end="")
    
    print("\n" + "-" * 40)
    print("✅ 所有文件下载完成")
    
    return True


def demo_directory_structure():
    """演示目录结构"""
    print("\n" + "=" * 60)
    print("📁 演示: 优化的目录结构")
    print("=" * 60)
    
    print("\n下载前:")
    print("temp/")
    print("├── video1/")
    print("│   ├── seg-001.ts")
    print("│   ├── seg-002.ts")
    print("│   └── ...")
    print("└── video2/")
    print("    ├── seg-001.ts")
    print("    └── ...")
    
    print("\n下载合并后:")
    print("output/")
    print("├── video1/")
    print("│   └── video1.mp4  ← 最终文件")
    print("├── video2/")
    print("│   └── video2.mp4  ← 最终文件")
    print("└── ...")
    
    print("\n临时目录清理:")
    print("✅ temp/video1/ 已删除")
    print("✅ temp/video2/ 已删除")
    
    return True


def demo_advanced_features():
    """演示高级功能"""
    print("\n" + "=" * 60)
    print("🚀 演示: 高级功能特性")
    print("=" * 60)
    
    print("\n1. 流式下载 (逐个下载):")
    print("   - 不再同时启动64个线程")
    print("   - 一个接一个下载，进度清晰")
    print("   - 实时显示每个文件的进度")
    
    print("\n2. JSON配置支持:")
    print("   - 批量管理多个下载任务")
    print("   - 支持自定义参数")
    print("   - 易于维护和分享")
    
    print("\n3. 智能目录管理:")
    print("   - temp/任务名/ 独立目录")
    print("   - 下载完成自动清理")
    print("   - 避免文件混乱")
    
    print("\n4. 实时进度显示:")
    print("   - 显示下载百分比")
    print("   - 显示字节数")
    print("   - 显示完成/失败统计")
    
    return True


def demo_usage_examples():
    """演示使用示例"""
    print("\n" + "=" * 60)
    print("💡 演示: 常用命令示例")
    print("=" * 60)
    
    examples = [
        ("单个下载", "python -m m3u8.advanced_cli https://example.com/video.m3u8"),
        ("指定输出", "python -m m3u8.advanced_cli https://example.com/video.m3u8 -o my.mp4"),
        ("快速模式", "python -m m3u8.advanced_cli https://example.com/video.m3u8 --profile fast"),
        ("JSON批量", "python -m m3u8.advanced_cli --json tasks.json"),
        ("交互模式", "python -m m3u8.advanced_cli -i"),
        ("自定义线程", "python -m m3u8.advanced_cli https://example.com/video.m3u8 --threads 16"),
    ]
    
    print("\n常用命令:")
    for title, cmd in examples:
        print(f"\n{title}:")
        print(f"  {cmd}")
    
    return True


def demo_programming_api():
    """演示编程API"""
    print("\n" + "=" * 60)
    print("💻 演示: 编程API使用")
    print("=" * 60)
    
    code_examples = [
        # 单个下载
        """
from m3u8.advanced_downloader import AdvancedM3U8Downloader
from m3u8.config import ConfigTemplates

config = ConfigTemplates.stable()
downloader = AdvancedM3U8Downloader(config)

success = downloader.download_single(
    name="my_video",
    url="https://example.com/video.m3u8",
    output_dir="./output/my_video"
)
        """,
        
        # JSON批量下载
        """
from m3u8.advanced_downloader import AdvancedM3U8Downloader
from m3u8.config import ConfigTemplates

config = ConfigTemplates.stable()
downloader = AdvancedM3U8Downloader(config)

success = downloader.download_from_json(
    json_file="tasks.json",
    base_output_dir="./output"
)
        """,
        
        # 自定义任务
        """
from m3u8.advanced_downloader import AdvancedM3U8Downloader, DownloadTask
from m3u8.config import DownloadConfig

config = DownloadConfig(num_threads=8)
downloader = AdvancedM3U8Downloader(config)

task = DownloadTask(
    name="custom",
    url="https://example.com/video.m3u8",
    output_dir="./output/custom",
    params={"quality": "1080p"}
)

success = downloader.manager.download_task(task)
        """
    ]
    
    print("\n代码示例:")
    for i, code in enumerate(code_examples, 1):
        print(f"\n{i}. {['单个下载', 'JSON批量', '自定义任务'][i-1]}:")
        print(code)
    
    return True


def main():
    """主演示函数"""
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "M3U8 Downloader Pro - 功能演示" + " " * 15 + "║")
    print("╚" + "═" * 58 + "╝")
    
    print("\n版本: v2.1.0")
    print("新特性: 流式下载 + JSON配置 + 实时进度")
    
    demos = [
        demo_json_config,
        demo_stream_progress,
        demo_directory_structure,
        demo_advanced_features,
        demo_usage_examples,
        demo_programming_api,
    ]
    
    for demo in demos:
        try:
            demo()
            input("\n按回车继续下一个演示...")
        except KeyboardInterrupt:
            print("\n\n演示已中断")
            break
        except Exception as e:
            print(f"\n❌ 演示出错: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 演示完成！")
    print("=" * 60)
    
    print("\n📚 更多信息:")
    print("- 查看 USAGE.md 获取详细使用指南")
    print("- 查看 README.md 了解项目详情")
    print("- 运行: python -m m3u8.advanced_cli -i 体验交互模式")
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
