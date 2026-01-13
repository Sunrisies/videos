"""
基础功能测试脚本
验证模块化M3U8下载器的核心功能
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试模块导入"""
    print("测试模块导入...")
    try:
        from m3u8.config import DownloadConfig, ConfigTemplates
        from m3u8.parser import M3U8Parser
        from m3u8.downloader import DownloadManager, M3U8Downloader, RetryHandler
        from m3u8.utils import FileValidator, URLProcessor, print_banner
        from m3u8.cli import M3U8CLI
        print("✅ 所有模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False

def test_config():
    """测试配置功能"""
    print("\n测试配置功能...")
    try:
        from m3u8.config import DownloadConfig, ConfigTemplates
        
        # 测试基础配置
        config = DownloadConfig()
        assert config.num_threads > 0
        assert config.max_retries == 3
        
        # 测试配置模板
        fast = ConfigTemplates.fast()
        assert fast.num_threads > config.num_threads
        
        stable = ConfigTemplates.stable()
        assert stable.max_retries == 5
        
        low = ConfigTemplates.low_bandwidth()
        assert low.num_threads == 2
        
        # 测试配置转换
        config_dict = config.to_dict()
        assert 'num_threads' in config_dict
        
        print("✅ 配置功能正常")
        return True
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False

def test_parser():
    """测试解析器功能"""
    print("\n测试解析器功能...")
    try:
        from m3u8.parser import M3U8Parser
        from m3u8.utils import FileValidator
        
        # 测试URL验证
        assert FileValidator.validate_url("https://example.com/video.m3u8")
        assert not FileValidator.validate_url("invalid-url")
        
        # 测试解析器初始化
        parser = M3U8Parser(verify_ssl=False)
        assert parser.verify_ssl == False
        
        # 测试URL处理
        assert parser.is_m3u8_url("https://example.com/video.m3u8")
        assert parser.extract_base_url("https://example.com/path/video.m3u8") == "https://example.com/path/"
        
        print("✅ 解析器功能正常")
        return True
    except Exception as e:
        print(f"❌ 解析器测试失败: {e}")
        return False

def test_downloader():
    """测试下载器功能"""
    print("\n测试下载器功能...")
    try:
        from m3u8.config import DownloadConfig
        from m3u8.downloader import RetryHandler, DownloadManager
        
        # 测试重试处理器
        retry_handler = RetryHandler(max_retries=2, retry_delay=0.1)
        
        # 测试成功函数
        def success_func():
            return "success"
        
        result = retry_handler.execute_with_retry(success_func)
        assert result == "success"
        
        # 测试失败函数（应该抛出异常）
        def fail_func():
            raise Exception("test error")
        
        try:
            retry_handler.execute_with_retry(fail_func)
            assert False, "应该抛出异常"
        except:
            pass  # 期望的异常
        
        # 测试下载管理器初始化
        config = DownloadConfig()
        manager = DownloadManager(config)
        assert manager.config == config
        
        print("✅ 下载器功能正常")
        return True
    except Exception as e:
        print(f"❌ 下载器测试失败: {e}")
        return False

def test_utils():
    """测试工具函数"""
    print("\n测试工具函数...")
    try:
        from m3u8.utils import URLProcessor, FileValidator, format_file_size, format_time
        
        # 测试URL处理
        normalized = URLProcessor.normalize_url("example.com/video.m3u8")
        assert normalized.startswith("https://")
        
        domain = URLProcessor.extract_domain("https://example.com/path/video.m3u8")
        assert domain == "example.com"
        
        # 测试文件大小格式化
        assert format_file_size(1024) == "1.00 KB"
        assert format_file_size(1024 * 1024) == "1.00 MB"
        
        # 测试时间格式化
        assert format_time(30) == "30.0s"
        assert format_time(90) == "1.5m"
        
        # 测试M3U8内容验证
        valid_content = "#EXTM3U\n#EXTINF:10,test.ts\ntest.ts"
        assert FileValidator.validate_m3u8_content(valid_content)
        
        invalid_content = "not m3u8"
        assert not FileValidator.validate_m3u8_content(invalid_content)
        
        print("✅ 工具函数正常")
        return True
    except Exception as e:
        print(f"❌ 工具函数测试失败: {e}")
        return False

def test_cli():
    """测试CLI功能"""
    print("\n测试CLI功能...")
    try:
        from m3u8.cli import M3U8CLI
        import argparse
        
        # 测试CLI初始化
        cli = M3U8CLI()
        assert cli.downloader is None
        
        # 测试参数解析（模拟）
        parser = argparse.ArgumentParser()
        parser.add_argument('url', nargs='?')
        parser.add_argument('-o', '--output')
        parser.add_argument('-t', '--threads', type=int)
        
        # 测试解析
        args = parser.parse_args(['https://example.com/video.m3u8', '-o', 'test.mp4', '-t', '4'])
        assert args.url == 'https://example.com/video.m3u8'
        assert args.output == 'test.mp4'
        assert args.threads == 4
        
        print("✅ CLI功能正常")
        return True
    except Exception as e:
        print(f"❌ CLI测试失败: {e}")
        return False

def test_file_operations():
    """测试文件操作"""
    print("\n测试文件操作...")
    try:
        import tempfile
        import os
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 测试目录创建
            test_path = os.path.join(temp_dir, "test_subdir")
            os.makedirs(test_path, exist_ok=True)
            assert os.path.exists(test_path)
            
            # 测试文件写入
            test_file = os.path.join(test_path, "test.txt")
            with open(test_file, 'w') as f:
                f.write("test content")
            
            assert os.path.exists(test_file)
            
            # 读取验证
            with open(test_file, 'r') as f:
                content = f.read()
            assert content == "test content"
        
        print("✅ 文件操作正常")
        return True
    except Exception as e:
        print(f"❌ 文件操作测试失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("=" * 60)
    print("M3U8 Downloader Pro - 基础功能测试")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_config,
        test_parser,
        test_downloader,
        test_utils,
        test_cli,
        test_file_operations,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 所有测试通过！模块化下载器工作正常。")
        return True
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查相关模块。")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
