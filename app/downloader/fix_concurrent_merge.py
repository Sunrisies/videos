#!/usr/bin/env python3
"""
快速修复脚本 - 解决并发FFmpeg合并问题

这个脚本会自动检测并修复现有的并发合并问题。
只需运行一次即可应用所有必要的修复。

使用方法:
    python fix_concurrent_merge.py
"""

import os
import sys
import shutil
from pathlib import Path

def print_header(text):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_step(step, total, text):
    """打印步骤"""
    print(f"\n[{step}/{total}] {text}")

def check_ffmpeg():
    """检查FFmpeg是否安装"""
    print_step(1, 5, "检查FFmpeg安装")
    
    try:
        import subprocess
        result = subprocess.run(
            ['ffmpeg', '-version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        print("✅ FFmpeg已安装")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFmpeg未安装或不可用")
        print("   请先安装FFmpeg:")
        print("   - Windows: https://ffmpeg.org/download.html")
        print("   - Linux:   sudo apt-get install ffmpeg")
        print("   - Mac:     brew install ffmpeg")
        return False

def backup_file(filepath):
    """备份文件"""
    if os.path.exists(filepath):
        backup = filepath + ".backup"
        shutil.copy2(filepath, backup)
        print(f"✅ 已备份: {backup}")
        return backup
    return None

def create_thread_safe_merge():
    """创建线程安全合并模块"""
    print_step(2, 5, "创建线程安全合并模块")
    
    content = '''"""
线程安全的文件合并模块 - 解决并发FFmpeg合并问题
"""

import os
import uuid
import threading
import subprocess
import logging
from typing import List, Optional
from pathlib import Path


class IsolatedMergeWorkspace:
    """隔离的合并工作空间"""
    
    def __init__(self, base_temp_dir: str, task_name: str):
        self.task_id = f"{task_name}_{uuid.uuid4().hex[:8]}"
        self.workspace = os.path.join(base_temp_dir, self.task_id)
        os.makedirs(self.workspace, exist_ok=True)
        
        self.file_list_path = os.path.join(
            self.workspace, 
            f"file_list_{self.task_id}.txt"
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"[{self.task_id}] 创建隔离工作空间: {self.workspace}")
    
    def cleanup(self):
        """清理工作空间"""
        try:
            if os.path.exists(self.workspace):
                import shutil
                shutil.rmtree(self.workspace)
                self.logger.info(f"[{self.task_id}] 工作空间已清理")
        except Exception as e:
            self.logger.warning(f"[{self.task_id}] 清理失败: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


class ThreadSafeFileMerger:
    """线程安全的文件合并器"""
    
    def __init__(self, config, logger=None, quiet_mode=False):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._quiet_mode = quiet_mode
        self._lock = threading.Lock()
        self._stop_flag = False
        
        # 确保临时目录存在
        self.base_temp_dir = os.path.join(
            config.temp_dir or "./temp", 
            "merge_workspaces"
        )
        os.makedirs(self.base_temp_dir, exist_ok=True)
    
    def set_stop_flag(self, stop_flag: bool):
        """设置停止标志"""
        with self._lock:
            self._stop_flag = stop_flag
    
    def _safe_print(self, message: str):
        """安全的打印函数"""
        if not self._quiet_mode:
            print(message)
    
    def _extract_filename(self, url: str) -> str:
        """从URL提取文件名"""
        return os.path.basename(url.split('?')[0])
    
    def _create_file_list(self, file_list: List[str], workspace: IsolatedMergeWorkspace) -> bool:
        """创建FFmpeg文件列表"""
        try:
            with open(workspace.file_list_path, 'w', encoding='utf-8') as f:
                for file_path in file_list:
                    # 如果是URL，提取文件名
                    if file_path.startswith('http'):
                        filename = self._extract_filename(file_path)
                        local_path = os.path.join(
                            os.path.dirname(workspace.workspace),
                            filename
                        )
                    else:
                        local_path = file_path
                    
                    if not os.path.exists(local_path):
                        self.logger.error(f"[{workspace.task_id}] 文件不存在: {local_path}")
                        return False
                    
                    abs_path = os.path.abspath(local_path)
                    escaped_path = abs_path.replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\\n")
            
            self.logger.info(f"[{workspace.task_id}] 文件列表创建成功: {len(file_list)} 个文件")
            return True
            
        except Exception as e:
            self.logger.error(f"[{workspace.task_id}] 创建文件列表失败: {e}")
            return False
    
    def merge_files(self, file_list: List[str], output_file: str, temp_dir: str) -> bool:
        """使用FFmpeg合并文件（线程安全版本）"""
        
        with self._lock:
            if self._stop_flag:
                return False
        
        # 按文件名排序
        sorted_files = sorted(file_list, key=lambda x: self._extract_filename(x))
        
        # 提取本地文件路径
        local_files = []
        for url in sorted_files:
            filename = self._extract_filename(url)
            filepath = os.path.join(temp_dir, filename)
            local_files.append(filepath)
        
        # 生成任务名称
        task_name = Path(output_file).stem
        
        # 创建隔离工作空间
        with IsolatedMergeWorkspace(self.base_temp_dir, task_name) as workspace:
            
            # 创建文件列表
            if not self._create_file_list(local_files, workspace):
                self._safe_print(f"❌ 创建文件列表失败")
                return self.merge_files_binary(sorted_files, output_file, temp_dir)
            
            # 构建FFmpeg命令
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', workspace.file_list_path,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',
                '-y',
                output_file
            ]
            
            self._safe_print(f"🔄 使用FFmpeg合并文件...")
            
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=600,
                    check=False
                )
                
                if result.returncode != 0:
                    stderr = result.stderr.decode('utf-8', errors='ignore')
                    self.logger.error(f"FFmpeg合并失败: {stderr}")
                    self._safe_print(f"⚠️ FFmpeg合并失败，尝试二进制合并...")
                    return self.merge_files_binary(sorted_files, output_file, temp_dir)
                
                # 清理临时文件
                self._cleanup_temp_files(local_files, temp_dir)
                
                self._safe_print(f"✅ 文件合并完成")
                return True
                
            except subprocess.TimeoutExpired:
                self._safe_print(f"❌ FFmpeg执行超时")
                return False
            except Exception as e:
                self.logger.error(f"合并异常: {e}")
                return False
    
    def merge_files_binary(self, sorted_files: List[str], output_file: str, temp_dir: str) -> bool:
        """二进制合并（线程安全版本）"""
        
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'wb') as outfile:
                for url in sorted_files:
                    with self._lock:
                        if self._stop_flag:
                            return False
                    
                    filename = self._extract_filename(url)
                    filepath = os.path.join(temp_dir, filename)
                    
                    if os.path.exists(filepath):
                        try:
                            with open(filepath, 'rb') as infile:
                                while True:
                                    chunk = infile.read(self.config.buffer_size)
                                    if not chunk:
                                        break
                                    outfile.write(chunk)
                        except Exception as e:
                            self.logger.warning(f"合并文件 {filepath} 时出错: {e}")
                            continue
            
            self._cleanup_temp_files(
                [os.path.join(temp_dir, self._extract_filename(url)) for url in sorted_files],
                temp_dir
            )
            
            self._safe_print(f"✅ 二进制合并完成")
            return True
            
        except Exception as e:
            self.logger.error(f"二进制合并失败: {e}")
            return False
    
    def _cleanup_temp_files(self, file_list: List[str], temp_dir: str):
        """清理临时文件"""
        for filepath in file_list:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"删除临时文件 {filepath} 失败: {e}")
        
        # 尝试清理临时目录
        try:
            if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)
        except:
            pass
    
    def merge_files_simple(self, file_list: List[str], output_file: str, temp_dir: str) -> bool:
        """简单的二进制合并（保持向后兼容）"""
        return self.merge_files_binary(file_list, output_file, temp_dir)


# 兼容性包装器
class CompatibleFileMerger:
    """完全兼容原有接口的包装器"""
    
    def __init__(self, config, logger=None, quiet_mode=False):
        self.config = config
        self.logger = logger
        self._quiet_mode = quiet_mode
        self.stop_flag = False
        
        self._merger = ThreadSafeFileMerger(config, logger, quiet_mode)
    
    def set_stop_flag(self, stop_flag: bool):
        self.stop_flag = stop_flag
        self._merger.set_stop_flag(stop_flag)
    
    def _extract_filename(self, url: str) -> str:
        return os.path.basename(url.split('?')[0])
    
    def _safe_print(self, message: str):
        if not self._quiet_mode:
            print(message)
    
    def merge_files(self, file_list: List[str], output_file: str, temp_dir: str) -> bool:
        """使用FFmpeg合并TS文件为MP4"""
        
        sorted_files = sorted(file_list, key=lambda x: self._extract_filename(x))
        
        # 提取本地文件路径
        local_files = []
        for url in sorted_files:
            filename = self._extract_filename(url)
            filepath = os.path.join(temp_dir, filename)
            local_files.append(filepath)
        
        task_name = Path(output_file).stem
        
        success = self._merger.merge_files(local_files, output_file, temp_dir)
        
        if success:
            self._safe_print(f"✅ 文件合并完成: {output_file}")
            return True
        else:
            self._safe_print(f"❌ 文件合并失败")
            return False
    
    def merge_files_binary(self, sorted_files: List[str], output_file: str, temp_dir: str) -> bool:
        """二进制合并"""
        return self._merger.merge_files_binary(sorted_files, output_file, temp_dir)
    
    def merge_files_simple(self, file_list: List[str], output_file: str, temp_dir: str) -> bool:
        """简单的二进制合并"""
        return self.merge_files_binary(file_list, output_file, temp_dir)
'''
    
    # 写入文件
    filepath = "app/downloader/core/thread_safe_merge.py"
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 已创建: {filepath}")
    return filepath

def update_advanced_downloader():
    """更新advanced_downloader.py使用新的合并器"""
    print_step(3, 5, "更新advanced_downloader.py")
    
    filepath = "app/downloader/core/advanced_downloader.py"
    
    if not os.path.exists(filepath):
        print("⚠️  文件不存在，跳过")
        return False
    
    # 备份
    backup_file(filepath)
    
    # 读取内容
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已经修复
    if "from .thread_safe_merge import" in content:
        print("✅ 已经使用线程安全合并器")
        return True
    
    # 修改导入
    old_import = "from .merge_files import FileMerger"
    new_import = "from .thread_safe_merge import CompatibleFileMerger as FileMerger"
    
    if old_import in content:
        content = content.replace(old_import, new_import)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ 已更新导入语句")
        return True
    else:
        print("⚠️  未找到原始导入语句，可能需要手动更新")
        return False

def create_test_script():
    """创建测试脚本"""
    print_step(4, 5, "创建测试脚本")
    
    content = '''#!/usr/bin/env python3
"""
并发合并测试脚本
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

from app.downloader.core.thread_safe_merge import ThreadSafeFileMerger
from app.downloader.core.config import DownloadConfig

def create_test_files(count=3):
    """创建测试文件"""
    temp_dir = tempfile.mkdtemp(prefix="test_merge_")
    files = []
    
    for i in range(count):
        filepath = os.path.join(temp_dir, f"segment_{i:03d}.ts")
        with open(filepath, 'wb') as f:
            # 写入最小TS文件头
            f.write(bytes([0x47, 0x40, 0x00, 0x10, 0x00]) + b'\\x00' * 183)
        files.append(filepath)
    
    return temp_dir, files

def test_single_merge():
    """测试单个合并"""
    print("\\n测试单个合并...")
    
    config = DownloadConfig()
    config.temp_dir = tempfile.mkdtemp(prefix="temp_")
    
    merger = ThreadSafeFileMerger(config)
    
    temp_dir, files = create_test_files(3)
    output = os.path.join(temp_dir, "output.mp4")
    
    success = merger.merge_files(files, output, temp_dir)
    
    # 清理
    shutil.rmtree(temp_dir, ignore_errors=True)
    shutil.rmtree(config.temp_dir, ignore_errors=True)
    
    return success

def test_concurrent_merges():
    """测试并发合并"""
    print("\\n测试并发合并...")
    
    from concurrent.futures import ThreadPoolExecutor
    
    config = DownloadConfig()
    config.temp_dir = tempfile.mkdtemp(prefix="temp_")
    
    def merge_task(task_id):
        merger = ThreadSafeFileMerger(config)
        temp_dir, files = create_test_files(3)
        output = os.path.join(temp_dir, f"output_{task_id}.mp4")
        
        success = merger.merge_files(files, output, temp_dir)
        
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return task_id, success
    
    # 并发执行
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(merge_task, i) for i in range(4)]
        results = [f.result() for f in futures]
    
    # 清理
    shutil.rmtree(config.temp_dir, ignore_errors=True)
    
    # 检查结果
    all_success = all(success for _, success in results)
    print(f"  结果: {sum(1 for _, s in results if s)}/4 成功")
    
    return all_success

if __name__ == "__main__":
    print("=" * 60)
    print("并发合并测试")
    print("=" * 60)
    
    try:
        # 测试1: 单个合并
        result1 = test_single_merge()
        print(f"单个合并: {'✅ 通过' if result1 else '❌ 失败'}")
        
        # 测试2: 并发合并
        result2 = test_concurrent_merges()
        print(f"并发合并: {'✅ 通过' if result2 else '❌ 失败'}")
        
        if result1 and result2:
            print("\\n🎉 所有测试通过！")
            sys.exit(0)
        else:
            print("\\n❌ 测试失败")
            sys.exit(1)
            
    except Exception as e:
        print(f"\\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
'''
    
    filepath = "app/downloader/test_fix.py"
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 使脚本可执行
    try:
        os.chmod(filepath, 0o755)
    except:
        pass
    
    print(f"✅ 已创建测试脚本: {filepath}")
    return filepath

def create_usage_example():
    """创建使用示例"""
    print_step(5, 5, "创建使用示例")
    
    content = '''#!/usr/bin/env python3
"""
使用示例 - 展示如何正确使用线程安全合并器
"""

import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

from app.downloader.core.thread_safe_merge import ThreadSafeFileMerger
from app.downloader.core.config import DownloadConfig

def main():
    print("=" * 70)
    print("线程安全合并器使用示例")
    print("=" * 70)
    
    # 1. 创建配置
    config = DownloadConfig()
    config.temp_dir = tempfile.mkdtemp(prefix="video_merge_")
    config.buffer_size = 8192
    
    print(f"\\n配置:")
    print(f"  临时目录: {config.temp_dir}")
    print(f"  缓冲区大小: {config.buffer_size}")
    
    # 2. 创建测试数据
    print(f"\\n创建测试数据...")
    
    def create_ts_files(task_name, count=3):
        """为任务创建TS文件"""
        task_dir = os.path.join(config.temp_dir, task_name)
        os.makedirs(task_dir, exist_ok=True)
        
        files = []
        for i in range(count):
            filepath = os.path.join(task_dir, f"segment_{i:03d}.ts")
            with open(filepath, 'wb') as f:
                f.write(bytes([0x47, 0x40, 0x00, 0x10, 0x00]) + b'\\x00' * 183)
            files.append(filepath)
        
        return files
    
    # 3. 创建多个任务
    tasks = [
        {"name": "video1", "output": "./output/video1.mp4"},
        {"name": "video2", "output": "./output/video2.mp4"},
        {"name": "video3", "output": "./output/video3.mp4"},
    ]
    
    # 4. 执行并发合并
    print(f"\\n开始并发合并 {len(tasks)} 个任务...")
    
    def merge_single_task(task):
        """合并单个任务"""
        task_name = task["name"]
        output_file = task["output"]
        
        # 创建TS文件
        files = create_ts_files(task_name, 3)
        
        # 创建合并器
        merger = ThreadSafeFileMerger(config)
        
        # 执行合并
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        success = merger.merge_files(files, output_file, config.temp_dir)
        
        return task_name, success
    
    # 使用线程池并发执行
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(merge_single_task, task): task["name"] for task in tasks}
        
        results = {}
        for future in futures:
            task_name = futures[future]
            try:
                name, success = future.result()
                results[name] = success
                status = "✅ 成功" if success else "❌ 失败"
                print(f"  {task_name}: {status}")
            except Exception as e:
                results[name] = False
                print(f"  {task_name}: ❌ 异常 - {e}")
    
    # 5. 总结
    success_count = sum(1 for v in results.values() if v)
    print(f"\\n结果: {success_count}/{len(tasks)} 成功")
    
    # 6. 验证输出
    print(f"\\n验证输出文件:")
    for task in tasks:
        output_file = task["output"]
        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            print(f"  ✅ {output_file}: {size:,} bytes")
        else:
            print(f"  ❌ {output_file}: 不存在")
    
    # 7. 清理
    print(f"\\n清理临时文件...")
    import shutil
    shutil.rmtree(config.temp_dir, ignore_errors=True)
    print("完成！")
    
    return all(results.values())

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
'''
    
    filepath = "app/downloader/example_usage.py"
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    try:
        os.chmod(filepath, 0o755)
    except:
        pass
    
    print(f"✅ 已创建使用示例: {filepath}")
    return filepath

def main():
    """主函数"""
    print_header("FFmpeg并发合并问题修复工具")
    
    print("""
这个工具将自动修复并发FFmpeg合并问题。
它会:
  1. 检查FFmpeg安装
  2. 创建线程安全合并模块
  3. 更新现有代码
  4. 创建测试脚本
  5. 创建使用示例
    
开始前请确保:
  - Python 3.7+
  - FFmpeg已安装
  - 在项目根目录运行此脚本
    """)
    
    # 确认继续
    response = input("是否继续? (y/n): ")
    if response.lower() != 'y':
        print("已取消")
        return
    
    # 执行修复
    steps = [
        check_ffmpeg,
        create_thread_safe_merge,
        update_advanced_downloader,
        create_test_script,
        create_usage_example,
    ]
    
    results = []
    for i, step in enumerate(steps, 1):
        try:
            result = step()
            results.append(result)
        except Exception as e:
            print(f"❌ 步骤 {i} 失败: {e}")
            results.append(False)
    
    # 总结
    print_header("修复完成")
    
    success_count = sum(1 for r in results if r)
    total = len(results)
    
    print(f"\n修复进度: {success_count}/{total} 完成")
    
    if success_count == total:
        print("\\n🎉 所有步骤完成！")
        print("\\n下一步:")
        print("  1. 运行测试: python app/downloader/test_fix.py")
        print("  2. 查看示例: python app/downloader/example_usage.py")
        print("  3. 阅读文档: app/downloader/docs/SOLUTION_SUMMARY.md")
    else:
        print("\\n⚠️  部分步骤失败，请手动检查")
        print("  详细信息请查看输出日志")

if __name__ == "__main__":
    main()