"""
聊天 API 接口
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from agent.api.common import (
    generate_session_id,
    handle_api_error
)
from agent.core.scheduler import AgentScheduler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["聊天"])

# 会话管理器 - 存储每个会话的调度器实例
schedulers: Dict[str, AgentScheduler] = {}


class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: str = Field(default_factory=generate_session_id, description="会话ID")
    message: str = Field(..., description="用户消息")
    video_path: Optional[str] = Field(default=None, description="视频路径（用于视频分析）")
    aspect_ratio: Optional[str] = Field(default="16:9", description="宽高比（用于视频生成）")
    duration: Optional[int] = Field(default=5, description="时长（用于视频生成）")
    resolution: Optional[str] = Field(default="720p", description="分辨率（用于视频生成）")


class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool
    session_id: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    message: Optional[str] = None
    result: Optional[Any] = None
    context_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def get_or_create_scheduler(session_id: str) -> AgentScheduler:
    """获取或创建调度器"""
    if session_id not in schedulers:
        logger.info(f"创建新的调度器实例 - session_id: {session_id}")
        schedulers[session_id] = AgentScheduler(
            session_id=session_id,
            use_llm_intent=True,
            context_compression_threshold=10000
        )
    return schedulers[session_id]


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    聊天接口
    
    工作流程：
    1. 接收用户消息
    2. 获取或创建会话调度器
    3. 调度器处理消息：
       - 意图识别
       - 上下文管理
       - 工具调度
    4. 返回结果
    
    支持的意图：
    - 视频生成: "生成一个视频..."
    - 视频分析: "分析这个视频..." (需要提供 video_path)
    - 帮助: "怎么使用？"
    - 普通对话: 其他
    """
    logger.info("=" * 80)
    logger.info("API 调用: /api/chat/")
    logger.info(f"入参: {request.model_dump()}")
    
    try:
        # 获取调度器
        scheduler = get_or_create_scheduler(request.session_id)
        
        # 构建参数
        kwargs = {
            "video_path": request.video_path,
            "aspect_ratio": request.aspect_ratio,
            "duration": request.duration,
            "resolution": request.resolution,
        }
        
        # 调用调度器处理
        logger.info(f"调用调度器处理消息: {request.message}")
        result = await scheduler.process(request.message, **kwargs)
        
        logger.info(f"调度器返回结果: {result}")
        
        # 构建响应
        response = ChatResponse(
            success=result.get("success", True),
            session_id=request.session_id,
            intent=result.get("intent"),
            confidence=result.get("confidence"),
            message=result.get("result", {}).get("message"),
            result=result.get("result"),
            context_info=result.get("context_info"),
            error=result.get("error")
        )
        
        logger.info(f"API 出参: {response.model_dump()}")
        logger.info("=" * 80)
        
        return response
        
    except Exception as e:
        logger.exception(f"聊天处理出错: {e}")
        raise handle_api_error(e)


@router.post("/clear")
async def clear_context(session_id: str):
    """
    清空会话上下文
    """
    logger.info(f"清空会话上下文 - session_id: {session_id}")
    
    if session_id in schedulers:
        schedulers[session_id].clear_context()
        return {
            "success": True,
            "message": f"会话 {session_id} 的上下文已清空"
        }
    else:
        return {
            "success": False,
            "message": f"会话 {session_id} 不存在"
        }


@router.get("/summary")
async def get_context_summary(session_id: str):
    """
    获取会话上下文摘要
    """
    logger.info(f"获取上下文摘要 - session_id: {session_id}")
    
    if session_id in schedulers:
        summary = schedulers[session_id].get_context_summary()
        return {
            "success": True,
            "summary": summary
        }
    else:
        return {
            "success": False,
            "message": f"会话 {session_id} 不存在"
        }


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """
    获取会话历史消息
    
    Args:
        session_id: 会话ID
    
    Returns:
        {
            "success": bool,
            "session_id": str,
            "messages": [{"role": str, "content": str, "timestamp": float}, ...],
            "metadata": {...},
            "error": str
        }
    """
    logger.info(f"API 调用: /api/chat/history/{session_id}")
    
    try:
        from pathlib import Path
        import json
        from agent.context.manager import DEFAULT_DATA_DIR
        
        # 会话目录
        session_dir = DEFAULT_DATA_DIR / session_id
        
        if not session_dir.exists():
            logger.warning(f"会话不存在: {session_id}")
            return {
                "success": False,
                "session_id": session_id,
                "messages": [],
                "error": "会话不存在"
            }
        
        # 读取元数据
        metadata_path = session_dir / "metadata.json"
        metadata = {}
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        
        # 读取向量存储（包含所有消息）
        vector_store_path = session_dir / "vector_store.json"
        messages = []
        
        if vector_store_path.exists():
            with open(vector_store_path, 'r', encoding='utf-8') as f:
                vector_data = json.load(f)
            
            # 提取消息
            for item in vector_data.get("items", []):
                content = item.get("content", "")
                item_metadata = item.get("metadata", {})
                
                # 解析消息格式 "[role] content"
                if content.startswith("["):
                    role_end = content.find("]")
                    if role_end > 0:
                        role = content[1:role_end]
                        message_content = content[role_end + 2:]  # 跳过 "] "
                        
                        messages.append({
                            "role": role,
                            "content": message_content,
                            "timestamp": item_metadata.get("timestamp", 0)
                        })
        
        # 按时间排序
        messages.sort(key=lambda x: x.get("timestamp", 0))
        
        logger.info(f"加载历史消息: {len(messages)} 条")
        
        return {
            "success": True,
            "session_id": session_id,
            "messages": messages,
            "metadata": metadata
        }
        
    except Exception as e:
        logger.exception(f"获取历史消息出错: {e}")
        return {
            "success": False,
            "session_id": session_id,
            "messages": [],
            "error": str(e)
        }

