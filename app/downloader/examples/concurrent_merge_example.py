#!/usr/bin/env python3
"""
并发FFmpeg合并视频的完整示例

这个示例展示了如何正确处理多个视频同时合并的问题，
确保每个合并操作完全独立，不会相互干扰。

运行前确保已安装：
pip install requests tqdm
"""

import os
import sys
import uuid
import logging
import threading
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s'
)

@dataclass
class MergeTask:
    """合并任务配置"""
    name: str
    input_files: List[str]  # TS文件路径列表
    output_dir: str         # 输出目录
    temp_base: str          # 临时目录基础路径

class IsolatedWorkspace:
    """隔离的工作空间，确保每个任务完全独立"""
    
    def __init__(self, base_dir: str, task_name: str):
        # 生成唯一ID
        self.task_id = f"{task_name}_{uuid.uuid4().hex[:8]}"
        self.workspace = os.path.join(base_dir, self.task_id)
        
        # 创建工作空间
        os.makedirs(self.workspace, exist_ok=True)
        
        # 生成唯一文件名
        self.file_list_path = os.path.join(self.workspace, f"file_list_{self.task_id}.txt")
        self.log_path = os.path.join(self.workspace, f"ffmpeg_{self.task_id}.log")
        
        logging.info(f"[{self.task_id}] 创建隔离工作空间: {self.workspace}")
    
    def cleanup(self):
        """清理工作空间"""
        try:
            if os.path.exists(self.workspace):
                import shutil
                shutil.rmtree(self.workspace)
                logging.info(f"[{self.task_id}] 清理工作空间完成")
        except Exception as e:
            logging.error(f"[{self.task_id}] 清理失败: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

class ThreadSafeMerger:
    """线程安全的FFmpeg合并器"""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self._lock = threading.Lock()
        self._stopped = False
    
    def create_file_list(self, input_files: List[str], workspace: IsolatedWorkspace) -> bool:
        """创建FFmpeg文件列表"""
        try:
            with open(workspace.file_list_path, 'w', encoding='utf-8') as f:
                for file_path in input_files:
                    if not os.path.exists(file_path):
                        logging.error(f"[{self.task_id}] 文件不存在: {file_path}")
                        return False
                    
                    # 使用绝对路径并转义
                    abs_path = os.path.abspath(file_path)
                    escaped_path = abs_path.replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
            
            logging.info(f"[{self.task_id}] 文件列表创建成功: {len(input_files)} 个文件")
            return True
            
        except Exception as e:
            logging.error(f"[{self.task_id}] 创建文件列表失败: {e}")
            return False
    
    def merge_with_ffmpeg(
        self, 
        input_files: List[str], 
        output_file: str,
        workspace: IsolatedWorkspace
    ) -> bool:
        """使用FFmpeg合并，完全隔离"""
        
        with self._lock:
            if self._stopped:
                logging.warning(f"[{self.task_id}] 合并已被取消")
                return False
            
            logging.info(f"[{self.task_id}] 开始合并到: {output_file}")
            
            # 1. 创建文件列表
            if not self.create_file_list(input_files, workspace):
                return False
            
            # 2. 构建FFmpeg命令
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', workspace.file_list_path,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',
                '-y',  # 覆盖输出
                output_file
            ]
            
            logging.info(f"[{self.task_id}] 执行命令: {' '.join(cmd)}")
            
            # 3. 执行合并
            try:
                # 使用管道捕获输出
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=300,  # 5分钟超时
                    check=False
                )
                
                # 记录FFmpeg输出
                if result.stdout:
                    logging.debug(f"[{self.task_id}] FFmpeg stdout: {result.stdout.decode()}")
                
                if result.stderr:
                    stderr = result.stderr.decode('utf-8', errors='ignore')
                    # 只记录错误级别以上的信息
                    if 'error' in stderr.lower():
                        logging.error(f"[{self.task_id}] FFmpeg错误: {stderr[:500]}")
                    else:
                        logging.debug(f"[{self.task_id}] FFmpeg stderr: {stderr[:500]}")
                
                if result.returncode != 0:
                    logging.error(f"[{self.task_id}] FFmpeg返回错误代码: {result.returncode}")
                    return False
                
                # 4. 验证输出
                if not os.path.exists(output_file):
                    logging.error(f"[{self.task_id}] 输出文件不存在: {output_file}")
                    return False
                
                file_size = os.path.getsize(output_file)
                if file_size == 0:
                    logging.error(f"[{self.task_id}] 输出文件为空")
                    os.remove(output_file)
                    return False
                
                logging.info(f"[{self.task_id}] 合并成功! 文件大小: {file_size:,} bytes")
                return True
                
            except subprocess.TimeoutExpired:
                logging.error(f"[{self.task_id}] FFmpeg执行超时")
                return False
            except Exception as e:
                logging.error(f"[{self.task_id}] 合并异常: {e}")
                return False
    
    def stop(self):
        """停止合并"""
        self._stopped = True

class ConcurrentMergeManager:
    """并发合并管理器"""
    
    def __init__(self, max_concurrent: int = 2, temp_base: Optional[str] = None):
        self.max_concurrent = max_concurrent
        self.temp_base = temp_base or os.path.join(os.getcwd(), "temp_merge")
        self._stop_flag = False
        
        # 确保临时目录存在
        os.makedirs(self.temp_base, exist_ok=True)
        
        logging.info(f"初始化并发合并管理器")
        logging.info(f"  最大并发数: {max_concurrent}")
        logging.info(f"  临时目录: {self.temp_base}")
    
    def merge_single_task(self, task: MergeTask) -> bool:
        """执行单个合并任务"""
        
        # 创建隔离工作空间
        with IsolatedWorkspace(self.temp_base, task.name) as workspace:
            
            # 确保输出目录存在
            os.makedirs(task.output_dir, exist_ok=True)
            output_file = os.path.join(task.output_dir, f"{task.name}.mp4")
            
            # 创建合并器
            merger = ThreadSafeMerger(workspace.task_id)
            
            # 执行合并
            success = merger.merge_with_ffmpeg(
                task.input_files,
                output_file,
                workspace
            )
            
            return success
    
    def merge_batch(self, tasks: List[MergeTask]) -> Dict[str, bool]:
        """批量合并多个任务"""
        
        logging.info(f"\n{'='*60}")
        logging.info(f"开始批量合并 {len(tasks)} 个任务")
        logging.info(f"{'='*60}\n")
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # 提交所有任务
            futures = {}
            for task in tasks:
                if self._stop_flag:
                    break
                
                future = executor.submit(self.merge_single_task, task)
                futures[future] = task.name
            
            # 收集结果
            for future in as_completed(futures):
                if self._stop_flag:
                    # 取消剩余任务
                    for f in futures:
                        f.cancel()
                    break
                
                task_name = futures[future]
                try:
                    success = future.result()
                    results[task_name] = success
                    status = "✅ 成功" if success else "❌ 失败"
                    logging.info(f"任务 {task_name}: {status}")
                except Exception as e:
                    results[task_name] = False
                    logging.error(f"任务 {task_name} 异常: {e}")
        
        # 总结
        success_count = sum(1 for v in results.values() if v)
        logging.info(f"\n{'='*60}")
        logging.info(f"合并完成: {success_count}/{len(tasks)} 成功")
        logging.info(f"{'='*60}\n")
        
        return results
    
    def stop(self):
        """停止所有任务"""
        self._stop_flag = True
        logging.warning("正在停止所有合并任务...")

def create_sample_files(base_dir: str, count: int) -> List[str]:
    """创建示例TS文件（用于测试）"""
    
    sample_dir = os.path.join(base_dir, "samples")
    os.makedirs(sample_dir, exist_ok=True)
    
    files = []
    for i in range(count):
        filepath = os.path.join(sample_dir, f"segment_{i:03d}.ts")
        
        # 创建一个最小的有效TS文件头
        # TS文件以0x47开头
        with open(filepath, 'wb') as f:
            # 写入TS包头（188字节）
            header = bytes([0x47, 0x40, 0x00, 0x10, 0x00]) + b'\x00' * 183
            f.write(header)
        
        files.append(filepath)
    
    logging.info(f"创建了 {len(files)} 个示例TS文件")
    return files

def main():
    """主函数 - 演示并发合并"""
    
    print("=" * 70)
    print("FFmpeg 并发合并视频演示")
    print("=" * 70)
    
    # 配置
    config = {
        'max_concurrent': 2,  # 最大并发合并数
        'temp_base': './temp_workspaces',
        'output_base': './output_videos',
        'task_count': 4,      # 要合并的任务数
        'segments_per_task': 5  # 每个任务的TS文件数
    }
    
    print(f"\n配置:")
    for k, v in config.items():
        print(f"  {k}: {v}")
    
    # 创建示例文件
    print(f"\n创建示例文件...")
    all_tasks = []
    
    for i in range(config['task_count']):
        task_name = f"video_{i+1}"
        
        # 为每个任务创建独立的TS文件
        task_files = create_sample_files(
            os.path.join(config['temp_base'], task_name),
            config['segments_per_task']
        )
        
        task = MergeTask(
            name=task_name,
            input_files=task_files,
            output_dir=config['output_base'],
            temp_base=config['temp_base']
        )
        all_tasks.append(task)
    
    # 执行合并
    print(f"\n开始并发合并...")
    start_time = time.time()
    
    manager = ConcurrentMergeManager(
        max_concurrent=config['max_concurrent'],
        temp_base=config['temp_base']
    )
    
    results = manager.merge_batch(all_tasks)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # 显示结果
    print(f"\n执行时间: {duration:.2f} 秒")
    print(f"平均时间: {duration/len(all_tasks):.2f} 秒/任务")
    
    # 验证输出文件
    print(f"\n验证输出文件:")
    for task in all_tasks:
        output_file = os.path.join(task.output_dir, f"{task.name}.mp4")
        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            print(f"  ✅ {task.name}.mp4: {size:,} bytes")
        else:
            print(f"  ❌ {task.name}.mp4: 不存在")
    
    # 清理示例文件
    print(f"\n清理示例文件...")
    try:
        import shutil
        if os.path.exists(config['temp_base']):
            shutil.rmtree(config['temp_base'])
        print("  临时目录已清理")
    except Exception as e:
        print(f"  清理警告: {e}")
    
    print(f"\n{'='*70}")
    print("演示完成!")
    print(f"{'='*70}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)