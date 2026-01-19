"""
多任务进度显示模块
实现类似 pip 的多任务并发进度条显示
"""

import sys
import threading
import time
from typing import Dict, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from tqdm import tqdm


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOAD_COMPLETED = "download_completed"  # 新增：下载完成
    MERGING = "merging"
    MERGE_COMPLETED = "merge_completed"         # 新增：合并完成
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskProgress:
    """单个任务的进度信息"""
    name: str
    total_segments: int = 0
    completed_segments: int = 0
    failed_segments: int = 0
    status: TaskStatus = TaskStatus.PENDING
    current_file: str = ""
    error_message: str = ""
    position: int = 0  # 进度条位置
    pbar: Optional[tqdm] = field(default=None, repr=False)

    @property
    def progress_percent(self) -> float:
        """计算进度百分比"""
        if self.total_segments == 0:
            return 0.0
        return (self.completed_segments / self.total_segments) * 100


class MultiTaskProgress:
    """
    多任务进度管理器

    支持同时显示多个任务的下载进度，类似 pip 的多包下载显示
    """

    def __init__(self, max_display_tasks: int = 6):
        """
        初始化进度管理器

        Args:
            max_display_tasks: 最大同时显示的任务数
        """
        self.max_display_tasks = max_display_tasks
        self._tasks: Dict[str, TaskProgress] = {}
        self._lock = threading.Lock()
        self._position_pool: List[int] = list(range(max_display_tasks))
        self._active_positions: Dict[str, int] = {}
        self._summary_position = max_display_tasks  # 汇总信息位置
        self._enabled = True
        self._summary_bar: Optional[tqdm] = None

    def __bool__(self):
        """
        确保MultiTaskProgress实例在布尔上下文中始终为True
        
        即使内部任务列表为空，进度管理器仍然有效
        """
        return True

    def enable(self):
        """启用进度显示"""
        self._enabled = True

    def disable(self):
        """禁用进度显示"""
        self._enabled = False

    def _allocate_position(self, task_name: str) -> int:
        """分配一个进度条位置"""
        with self._lock:
            if task_name in self._active_positions:
                return self._active_positions[task_name]

            if self._position_pool:
                pos = self._position_pool.pop(0)
                self._active_positions[task_name] = pos
                return pos

            # 没有可用位置，返回 -1 表示不显示进度条
            return -1

    def _release_position(self, task_name: str):
        """释放进度条位置"""
        with self._lock:
            if task_name in self._active_positions:
                pos = self._active_positions.pop(task_name)
                self._position_pool.append(pos)
                self._position_pool.sort()

    def register_task(self, task_name: str, total_segments: int) -> TaskProgress:
        """
        注册一个新任务

        Args:
            task_name: 任务名称
            total_segments: 总片段数

        Returns:
            TaskProgress: 任务进度对象
        """
        position = self._allocate_position(task_name)

        task = TaskProgress(
            name=task_name,
            total_segments=total_segments,
            position=position,
            status=TaskStatus.PENDING
        )

        with self._lock:
            self._tasks[task_name] = task

        # 创建进度条
        if self._enabled and position >= 0:
            # 确保即使初始总数为0也能正确显示
            actual_total = total_segments if total_segments > 0 else 1  # 至少为1，避免tqdm问题
            task.pbar = tqdm(
                total=actual_total,
                desc=self._format_desc(task_name, TaskStatus.PENDING),
                position=position,
                leave=False,
                ncols=70,
                file=sys.stderr,
                mininterval=0.3,
                bar_format='{desc} {bar} {n_fmt}/{total_fmt}'
            )
            # 如果初始总数为0，手动设置为0显示
            if total_segments == 0:
                task.pbar.n = 0
                task.pbar.refresh()

        return task

    def _format_desc(self, task_name: str, status: TaskStatus, extra: str = "") -> str:
        """格式化任务描述"""
        # 状态图标
        status_icons = {
            TaskStatus.PENDING: "○",
            TaskStatus.DOWNLOADING: "↓",
            TaskStatus.DOWNLOAD_COMPLETED: "↑",  # 下载完成
            TaskStatus.MERGING: "◎",
            TaskStatus.MERGE_COMPLETED: "⊕",     # 合并完成
            TaskStatus.COMPLETED: "✓",
            TaskStatus.FAILED: "✗",
        }
        icon = status_icons.get(status, " ")

        # 截断过长的任务名
        max_name_len = 15
        if len(task_name) > max_name_len:
            display_name = task_name[:max_name_len-2] + ".."
        else:
            display_name = task_name.ljust(max_name_len)

        desc = f"{icon} {display_name}"
        if extra:
            desc += f" {extra}"

        return desc

    def update_task(
        self,
        task_name: str,
        completed: int = None,
        failed: int = None,
        status: TaskStatus = None,
        current_file: str = None
    ):
        """
        更新任务进度

        Args:
            task_name: 任务名称
            completed: 已完成片段数
            failed: 失败片段数
            status: 任务状态
            current_file: 当前下载的文件名
        """
        with self._lock:
            if task_name not in self._tasks:
                return

            task = self._tasks[task_name]

            if completed is not None:
                task.completed_segments = completed
            if failed is not None:
                task.failed_segments = failed
            if status is not None:
                task.status = status
            if current_file is not None:
                task.current_file = current_file

        # 更新进度条
        if self._enabled and task.pbar:
            extra = ""
            if task.failed_segments > 0:
                extra = f"({task.failed_segments} failed)"

            task.pbar.set_description(
                self._format_desc(task_name, task.status, extra))
            task.pbar.n = task.completed_segments + task.failed_segments
            task.pbar.refresh()

    def increment_task(self, task_name: str, success: bool = True):
        """
        增加任务进度

        Args:
            task_name: 任务名称
            success: 是否成功
        """
        with self._lock:
            if task_name not in self._tasks:
                return

            task = self._tasks[task_name]

            if success:
                task.completed_segments += 1
            else:
                task.failed_segments += 1

        # 更新进度条
        if self._enabled and task.pbar:
            extra = ""
            if task.failed_segments > 0:
                extra = f"({task.failed_segments} failed)"

            task.pbar.set_description(
                self._format_desc(task_name, task.status, extra))
            task.pbar.update(1)

    def complete_task(self, task_name: str, success: bool = True, message: str = ""):
        """
        标记任务完成

        Args:
            task_name: 任务名称
            success: 是否成功
            message: 完成消息
        """
        with self._lock:
            if task_name not in self._tasks:
                return

            task = self._tasks[task_name]
            task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            task.error_message = message

        # 关闭进度条并显示最终状态
        if self._enabled and task.pbar:
            status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            final_desc = self._format_desc(task_name, status, message)
            task.pbar.set_description(final_desc)
            task.pbar.close()
            task.pbar = None

        # 释放位置
        self._release_position(task_name)

    def get_task(self, task_name: str) -> Optional[TaskProgress]:
        """获取任务进度"""
        with self._lock:
            return self._tasks.get(task_name)

    def get_summary(self) -> Dict:
        """获取所有任务的汇总信息"""
        with self._lock:
            total_tasks = len(self._tasks)
            completed = sum(1 for t in self._tasks.values()
                            if t.status == TaskStatus.COMPLETED)
            failed = sum(1 for t in self._tasks.values()
                         if t.status == TaskStatus.FAILED)
            in_progress = sum(1 for t in self._tasks.values() if t.status in (
                TaskStatus.DOWNLOADING, TaskStatus.MERGING, TaskStatus.DOWNLOAD_COMPLETED))

            return {
                'total': total_tasks,
                'completed': completed,
                'failed': failed,
                'in_progress': in_progress,
                'pending': total_tasks - completed - failed - in_progress
            }

    def print_summary(self):
        """打印汇总信息"""
        summary = self.get_summary()

        print(f"\n{'='*60}")
        print("📊 下载任务汇总")
        print(f"{'='*60}")
        print(f"  总任务数: {summary['total']}")
        print(f"  ✅ 成功: {summary['completed']}")
        print(f"  ❌ 失败: {summary['failed']}")
        if summary['in_progress'] > 0:
            print(f"  ⏳ 进行中: {summary['in_progress']}")
        print(f"  📁 待处理: {summary['pending']}")
        print(f"{'='*60}\n")

    def clear(self):
        """清理所有任务"""
        with self._lock:
            for task in self._tasks.values():
                if task.pbar:
                    task.pbar.close()
            self._tasks.clear()
            self._active_positions.clear()
            self._position_pool = list(range(self.max_display_tasks))


class SegmentProgressTracker:
    """
    片段下载进度跟踪器

    用于跟踪单个任务中所有片段的下载进度
    """

    def __init__(self, task_name: str, total_segments: int, progress_manager: MultiTaskProgress):
        """
        初始化片段跟踪器

        Args:
            task_name: 任务名称
            total_segments: 总片段数
            progress_manager: 进度管理器
        """
        self.task_name = task_name
        self.total_segments = total_segments
        self.progress_manager = progress_manager
        self._completed = 0
        self._failed = 0
        self._lock = threading.Lock()

    def update_total_segments(self, new_total: int):
        """更新总片段数"""
        with self._lock:
            self.total_segments = new_total
            # 同时更新进度管理器中的任务信息
            task_progress = self.progress_manager.get_task(self.task_name)
            if task_progress:
                task_progress.total_segments = new_total
                if task_progress.pbar:
                    task_progress.pbar.total = new_total
                    # 更新进度条的显示，确保显示正确的总数
                    task_progress.pbar.refresh()

    def start_download(self):
        """开始下载阶段"""
        self.progress_manager.update_task(
            self.task_name,
            status=TaskStatus.DOWNLOADING
        )

    def on_segment_complete(self, success: bool = True, filename: str = ""):
        """
        片段下载完成回调

        Args:
            success: 是否成功
            filename: 文件名
        """
        with self._lock:
            if success:
                self._completed += 1
            else:
                self._failed += 1

        self.progress_manager.increment_task(self.task_name, success)
        
        # 检查是否所有片段都下载完成
        if self._completed + self._failed >= self.total_segments:
            self.progress_manager.update_task(
                self.task_name,
                status=TaskStatus.DOWNLOAD_COMPLETED
            )

    def start_merge(self):
        """开始合并阶段"""
        self.progress_manager.update_task(
            self.task_name,
            status=TaskStatus.MERGING
        )

    def on_merge_complete(self, success: bool = True, message: str = ""):
        """合并完成"""
        if success:
            self.progress_manager.update_task(
                self.task_name,
                status=TaskStatus.MERGE_COMPLETED
            )
        else:
            self.progress_manager.update_task(
                self.task_name,
                status=TaskStatus.FAILED
            )
            
        # 最终完成状态
        final_status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        self.progress_manager.complete_task(self.task_name, success, message)

    def finish(self, success: bool = True, message: str = ""):
        """完成跟踪 - 完成整个任务"""
        self.progress_manager.complete_task(self.task_name, success, message)

    @property
    def completed(self) -> int:
        """已完成数"""
        return self._completed

    @property
    def failed(self) -> int:
        """失败数"""
        return self._failed


def create_simple_progress_bar(
    total: int,
    desc: str = "Progress",
    position: int = 0
) -> tqdm:
    """
    创建简单进度条

    Args:
        total: 总数
        desc: 描述
        position: 位置

    Returns:
        tqdm: 进度条对象
    """
    return tqdm(
        total=total,
        desc=desc,
        position=position,
        leave=True,
        ncols=100,
        bar_format='{desc} |{bar}| {n_fmt}/{total_fmt} [{percentage:3.0f}%] {elapsed}<{remaining}'
    )