"""
上下文数据清理器
定期清理过期的会话数据
"""

import os
import time
from pathlib import Path
from typing import Optional
import asyncio


class ContextCleaner:
    """
    上下文清理器
    
    功能：
    1. 扫描 context/data 目录
    2. 检查文件修改时间
    3. 删除超过指定天数未修改的文件
    """
    
    def __init__(
        self,
        data_dir: Optional[Path] = None,
        max_age_days: int = 30,
        cleanup_interval_hours: int = 24
    ):
        """
        初始化清理器
        
        Args:
            data_dir: 数据目录，默认为 context/data
            max_age_days: 最大保留天数
            cleanup_interval_hours: 清理间隔（小时）
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        
        self.data_dir = data_dir
        self.max_age_days = max_age_days
        self.cleanup_interval_hours = cleanup_interval_hours
        self.max_age_seconds = max_age_days * 24 * 3600
        
        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def scan_expired_files(self) -> list[Path]:
        """
        扫描过期文件
        
        Returns:
            过期文件路径列表
        """
        expired_files = []
        current_time = time.time()
        
        if not self.data_dir.exists():
            return expired_files
        
        # 遍历所有文件
        for file_path in self.data_dir.rglob("*"):
            if file_path.is_file() and file_path.name != ".gitignore":
                # 获取文件最后修改时间
                mtime = file_path.stat().st_mtime
                age_seconds = current_time - mtime
                
                # 检查是否过期
                if age_seconds > self.max_age_seconds:
                    expired_files.append(file_path)
        
        return expired_files
    
    def cleanup_expired_files(self) -> dict:
        """
        清理过期文件
        
        Returns:
            清理统计信息
        """
        expired_files = self.scan_expired_files()
        
        deleted_count = 0
        deleted_size = 0
        errors = []
        
        for file_path in expired_files:
            try:
                # 记录文件大小
                file_size = file_path.stat().st_size
                
                # 删除文件
                file_path.unlink()
                
                deleted_count += 1
                deleted_size += file_size
                
                print(f"[清理器] 已删除过期文件: {file_path.name} "
                      f"(年龄: {(time.time() - file_path.stat().st_mtime) / 86400:.1f}天)")
                
            except Exception as e:
                errors.append({
                    "file": str(file_path),
                    "error": str(e)
                })
        
        # 清理空目录
        self._cleanup_empty_dirs()
        
        return {
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "deleted_size_mb": deleted_size / (1024 * 1024),
            "errors": errors,
            "timestamp": time.time()
        }
    
    def _cleanup_empty_dirs(self):
        """清理空目录"""
        for dir_path in sorted(self.data_dir.rglob("*"), reverse=True):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                try:
                    dir_path.rmdir()
                    print(f"[清理器] 已删除空目录: {dir_path.name}")
                except Exception as e:
                    print(f"[清理器] 删除空目录失败 {dir_path}: {e}")
    
    def get_storage_stats(self) -> dict:
        """
        获取存储统计信息
        
        Returns:
            统计信息
        """
        total_files = 0
        total_size = 0
        expired_files = 0
        sessions = set()
        
        current_time = time.time()
        
        for file_path in self.data_dir.rglob("*"):
            if file_path.is_file() and file_path.name != ".gitignore":
                total_files += 1
                total_size += file_path.stat().st_size
                
                # 检查是否过期
                mtime = file_path.stat().st_mtime
                age_seconds = current_time - mtime
                if age_seconds > self.max_age_seconds:
                    expired_files += 1
                
                # 提取会话ID（假设文件名格式为 xxx_session_id.json）
                parts = file_path.stem.split("_")
                if len(parts) >= 2:
                    sessions.add(parts[-1])
        
        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "expired_files": expired_files,
            "active_sessions": len(sessions),
            "max_age_days": self.max_age_days
        }
    
    async def run_periodic_cleanup(self):
        """
        运行定期清理任务（异步）
        """
        print(f"[清理器] 启动定期清理任务 (间隔: {self.cleanup_interval_hours}小时, "
              f"最大年龄: {self.max_age_days}天)")
        
        while True:
            try:
                # 执行清理
                result = self.cleanup_expired_files()
                
                if result["deleted_count"] > 0:
                    print(f"[清理器] 清理完成: 删除 {result['deleted_count']} 个文件, "
                          f"释放 {result['deleted_size_mb']:.2f} MB")
                else:
                    print(f"[清理器] 无过期文件需要清理")
                
                # 显示存储统计
                stats = self.get_storage_stats()
                print(f"[清理器] 存储状态: {stats['total_files']} 个文件, "
                      f"{stats['total_size_mb']:.2f} MB, "
                      f"{stats['active_sessions']} 个活跃会话")
                
            except Exception as e:
                print(f"[清理器] 清理任务出错: {e}")
            
            # 等待下次清理
            await asyncio.sleep(self.cleanup_interval_hours * 3600)
    
    def force_cleanup_session(self, session_id: str) -> dict:
        """
        强制清理指定会话的数据
        
        Args:
            session_id: 会话ID
        
        Returns:
            清理结果
        """
        deleted_count = 0
        deleted_size = 0
        errors = []
        
        # 查找该会话的所有文件
        pattern = f"*_{session_id}.*"
        
        for file_path in self.data_dir.glob(pattern):
            if file_path.is_file():
                try:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    
                    deleted_count += 1
                    deleted_size += file_size
                    
                except Exception as e:
                    errors.append({
                        "file": str(file_path),
                        "error": str(e)
                    })
        
        return {
            "session_id": session_id,
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "errors": errors
        }


# 全局清理器实例
_global_cleaner = None


def get_cleaner(
    max_age_days: int = 30,
    cleanup_interval_hours: int = 24
) -> ContextCleaner:
    """
    获取全局清理器实例
    
    Args:
        max_age_days: 最大保留天数
        cleanup_interval_hours: 清理间隔（小时）
    
    Returns:
        ContextCleaner实例
    """
    global _global_cleaner
    
    if _global_cleaner is None:
        _global_cleaner = ContextCleaner(
            max_age_days=max_age_days,
            cleanup_interval_hours=cleanup_interval_hours
        )
    
    return _global_cleaner


# 使用示例
if __name__ == "__main__":
    import asyncio
    
    async def test():
        cleaner = ContextCleaner(max_age_days=30, cleanup_interval_hours=24)
        
        # 获取存储统计
        stats = cleaner.get_storage_stats()
        print(f"存储统计: {stats}")
        
        # 扫描过期文件
        expired = cleaner.scan_expired_files()
        print(f"过期文件: {len(expired)}")
        
        # 执行清理
        result = cleaner.cleanup_expired_files()
        print(f"清理结果: {result}")
    
    asyncio.run(test())

