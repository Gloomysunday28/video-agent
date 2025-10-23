"""
SSE (Server-Sent Events) 管理模块
"""
import asyncio
import json
from typing import Dict, Any, List

# 支持同一 session 多连接
sse_connections: Dict[str, List[asyncio.Queue]] = {}

async def send_sse_message(session_id: str, message: Dict[str, Any]):
    """发送SSE消息"""
    queues = sse_connections.get(session_id, [])
    stale: List[asyncio.Queue] = []
    for q in queues:
        try:
            await q.put(message)
        except Exception as e:
            print(f"发送SSE消息失败: {e}")
            stale.append(q)
    if stale:
        for q in stale:
            try:
                sse_connections.get(session_id, []).remove(q)
            except ValueError:
                pass

def register_connection(session_id: str) -> asyncio.Queue:
    """注册一个新的SSE连接并返回其队列"""
    q: asyncio.Queue = asyncio.Queue()
    if session_id not in sse_connections:
        sse_connections[session_id] = []
    sse_connections[session_id].append(q)
    return q

def unregister_connection(session_id: str, q: asyncio.Queue) -> None:
    """注销SSE连接"""
    try:
        if session_id in sse_connections:
            sse_connections[session_id].remove(q)
            if not sse_connections[session_id]:
                del sse_connections[session_id]
    except ValueError:
        pass

def get_sse_connections():
    """获取SSE连接管理器（仅用于调试）"""
    return sse_connections

# 兼容性辅助函数：用于视频任务状态推进（原先基于 WebSocket）
async def send_task_status(session_id: str, task_id: str, status: str, message: str, extra: Dict[str, Any] | None = None):
    payload: Dict[str, Any] = {
        "type": "task_status",
        "task_id": task_id,
        "status": status,
        "message": message,
    }
    if extra:
        payload.update(extra)
    await send_sse_message(session_id, payload)

async def send_task_progress(session_id: str, task_id: str, progress: float, message: str, extra: Dict[str, Any] | None = None):
    payload: Dict[str, Any] = {
        "type": "task_progress",
        "task_id": task_id,
        "progress": progress,
        "message": message,
    }
    if extra:
        payload.update(extra)
    await send_sse_message(session_id, payload)

async def send_task_error(session_id: str, task_id: str, error_message: str, data: Dict[str, Any] | None = None):
    payload: Dict[str, Any] = {
        "type": "task_status",
        "task_id": task_id,
        "status": "failed",
        "message": error_message,
    }
    if data:
        payload["data"] = data
    await send_sse_message(session_id, payload)

async def send_task_completed(session_id: str, task_id: str, message: str, data: Dict[str, Any] | None = None):
    payload: Dict[str, Any] = {
        "type": "task_status",
        "task_id": task_id,
        "status": "completed",
        "message": message,
        "progress": 100,
    }
    if data:
        payload["data"] = data
    await send_sse_message(session_id, payload)
