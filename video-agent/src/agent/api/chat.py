"""
聊天 API 接口
"""

from fastapi import APIRouter, Query, Form
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
import json

from agent.api.common import (
    generate_session_id,
    handle_api_error
)
from agent.core.scheduler import AgentScheduler
from agent.api.sse import send_sse_message, register_connection, unregister_connection
import uuid
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["聊天"])

# 会话管理器 - 存储每个会话的调度器实例
schedulers: Dict[str, AgentScheduler] = {}


class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: str = Field(default_factory=generate_session_id, description="会话ID")
    message: str = Field(..., description="用户消息")
    video_path: Optional[str] = Field(default=None, description="视频路径（用于视频分析）")
    video_file: Optional[str] = Field(default=None, description="视频文件base64（用于视频分析）")
    video_filename: Optional[str] = Field(default=None, description="视频文件名")
    image_file: Optional[str] = Field(default=None, description="图片文件base64（用于多模态图片生成）")
    image_filename: Optional[str] = Field(default=None, description="图片文件名")
    aspect_ratio: Optional[str] = Field(default="16:9", description="宽高比（用于视频生成）")
    duration: Optional[int] = Field(default=5, description="时长（用于视频生成）")
    resolution: Optional[str] = Field(default="720p", description="分辨率（用于视频生成）")
    generator_type: Optional[str] = Field(default="doubao", description="生成器类型: jianying(剪映API)、doubao(豆包API，实际使用bantouyan)、bantouyan(Bantouyan API)、replicate(Replicate) 或 script(脚本调用)")
    script_path: Optional[str] = Field(default=None, description="脚本路径（当generator_type为script时使用）")
    # 豆包参数
    doubao_api_key: Optional[str] = Field(default=None, description="豆包 API Key")


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
    聊天接口（支持SSE状态推送）
    
    工作流程：
    1. 接收用户消息
    2. 获取或创建会话调度器
    3. 调度器处理消息：
       - 意图识别
       - 上下文管理
       - 工具调度
    4. 返回结果
    5. 通过SSE推送状态更新
    
    支持的意图：
    - 视频生成: "生成一个视频..."
    - 视频分析: "分析这个视频..." (需要提供 video_path)
    - 帮助: "怎么使用？"
    - 普通对话: 其他
    """
    task_id = str(uuid.uuid4())
    
    logger.info("=" * 80)
    logger.info("API 调用: /api/chat/")
    logger.info(f"入参: {request.model_dump()}")
    
    try:
        # 发送任务开始状态
        await send_sse_message(request.session_id, {
            "type": "task_status",
            "task_id": task_id,
            "status": "pending",
            "message": "正在处理您的消息...",
            "timestamp": datetime.now().isoformat()
        })

        # 获取调度器
        scheduler = get_or_create_scheduler(request.session_id)

        await send_sse_message(request.session_id, {
            "type": "task_progress",
            "task_id": task_id,
            "progress": 20.0,
            "message": "正在分析您的意图...",
            "timestamp": datetime.now().isoformat()
        })

        # 构建参数
        kwargs = {
            "video_path": request.video_path,
            "video_file": request.video_file,
            "video_filename": request.video_filename,
            "image_file": request.image_file,
            "image_filename": request.image_filename,
            "aspect_ratio": request.aspect_ratio,
            "duration": request.duration,
            "resolution": request.resolution,
            "generator_type": request.generator_type,
            "script_path": request.script_path,
        }

        async def process_task():
            try:
                logger.info(f"调用调度器处理消息: {request.message}")
                result = await scheduler.process(request.message, **kwargs)
                logger.info(f"调度器返回结果: {result}")

                # 进度更新
                await send_sse_message(request.session_id, {
                    "type": "task_progress",
                    "task_id": task_id,
                    "progress": 90.0,
                    "message": "处理完成，正在返回结果...",
                    "timestamp": datetime.now().isoformat()
                })

                # 完成/失败
                print(f"[聊天API] 收到调度器结果: {result}")
                if result.get("success", True):
                    await send_sse_message(request.session_id, {
                        "type": "task_status",
                        "task_id": task_id,
                        "status": "completed",
                        "message": "消息处理完成",
                        "progress": 100,
                        "timestamp": datetime.now().isoformat()
                    })

                    # 构造最终回复
                    # 直接提取URL（所有生成器现在都返回统一格式的URL字符串）
                    video_path = result.get('result', {}).get('video_path') or result.get('video_path')
                    video_url = result.get('result', {}).get('video_url') or result.get('video_url')
                    image_url = result.get('result', {}).get('image_url') or result.get('image_url')
                    content = result.get("result", {}).get("message") or result.get("message") or "任务已完成"
                    
                    # 确定消息类型
                    message_type = "text"
                    print(f"[聊天API] 调试信息 - intent: {result.get('intent')}, image_url: {image_url}, video_url: {video_url}, video_path: {video_path}")
                    print(f"[聊天API] 完整result: {result}")
                    
                    if result.get("intent") == "generate_image":
                        message_type = "image"
                        # 对于图片消息，content 直接是图片URL，不需要额外的文案
                        content = image_url or video_url or video_path
                        print(f"[聊天API] 设置为图片消息 - content: {content}")
                    elif video_path or video_url:
                        message_type = "video"
                        # 对于视频消息，content 直接是视频URL，不需要额外的文案
                        content = video_url or video_path
                        print(f"[聊天API] 设置为视频消息 - content: {content}")
                    
                    print(f"[聊天API] 最终消息类型: {message_type}, 内容: {content}")

                    await send_sse_message(request.session_id, {
                        "type": "assistant_reply",
                        "task_id": task_id,
                        "content": content,
                        "message_type": message_type,
                        "timestamp": datetime.now().isoformat(),
                        "data": {
                            "success": True,
                            "session_id": request.session_id,
                            "task_id": task_id,
                            **result
                        }
                    })
                else:
                    # 发送失败状态
                    await send_sse_message(request.session_id, {
                        "type": "task_status",
                        "task_id": task_id,
                        "status": "failed",
                        "message": result.get("error", "处理失败"),
                        "progress": 0,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # 发送失败的assistant_reply
                    error_message = result.get("message", result.get("error", "处理失败，请稍后重试"))
                    await send_sse_message(request.session_id, {
                        "type": "assistant_reply",
                        "task_id": task_id,
                        "content": error_message,
                        "message_type": "text",
                        "timestamp": datetime.now().isoformat(),
                        "data": {
                            "success": False,
                            "session_id": request.session_id,
                            "task_id": task_id,
                            **result
                        }
                    })
            except Exception as e:
                logger.exception(f"后台任务处理出错: {e}")
                await send_sse_message(request.session_id, {
                    "type": "task_status",
                    "task_id": task_id,
                    "status": "failed",
                    "message": str(e),
                    "progress": 0,
                    "timestamp": datetime.now().isoformat()
                })

        # 后台运行，不阻塞请求
        asyncio.create_task(process_task())

        # 立即返回接受状态
        response = ChatResponse(
            success=True,
            session_id=request.session_id,
            message="任务已开始处理",
        )
        response_dict = response.model_dump()
        response_dict["task_id"] = task_id
        return response_dict

    except Exception as e:
        logger.exception(f"聊天处理出错: {e}")
        raise handle_api_error(e)



class StreamChatRequest(BaseModel):
    """流式聊天请求"""
    message: str = Field(..., description="用户消息")
    session_id: str = Field(default_factory=generate_session_id, description="会话ID")
    video_path: Optional[str] = Field(default=None, description="视频路径")
    video_file: Optional[str] = Field(default=None, description="视频文件base64")
    video_filename: Optional[str] = Field(default=None, description="视频文件名")
    image_file: Optional[str] = Field(default=None, description="图片文件base64")
    image_filename: Optional[str] = Field(default=None, description="图片文件名")
    aspect_ratio: Optional[str] = Field(default="16:9", description="宽高比")
    duration: Optional[int] = Field(default=5, description="时长")
    resolution: Optional[str] = Field(default="720p", description="分辨率")
    generator_type: Optional[str] = Field(default="doubao", description="生成器类型")
    script_path: Optional[str] = Field(default=None, description="脚本路径")


@router.post("/stream")
async def chat_stream_post(request: StreamChatRequest):
    """基于 SSE 的流式对话接口（POST方法，同一连接内推送事件）"""
    from fastapi.responses import StreamingResponse

    task_id = str(uuid.uuid4())
    session_id = request.session_id
    message = request.message

    async def event_generator():
        # 为该 session 注册一个临时连接队列
        connection_queue = register_connection(session_id)

        try:
            # 连接确认
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

            # 发送任务开始
            await send_sse_message(session_id, {
                'type': 'task_status',
                'task_id': task_id,
                'status': 'pending',
                'message': '正在处理您的消息...',
                'timestamp': datetime.now().isoformat()
            })

            
            # 后台执行调度
            scheduler = get_or_create_scheduler(session_id)
            kwargs = {
                'video_path': request.video_path,
                'video_file': request.video_file,
                'video_filename': request.video_filename,
                'image_file': request.image_file,
                'image_filename': request.image_filename,
                'aspect_ratio': request.aspect_ratio,
                'duration': request.duration,
                'resolution': request.resolution,
                'generator_type': request.generator_type,
                'script_path': request.script_path,
            }

            async def process_task():
                try:
                    await send_sse_message(session_id, {
                        'type': 'task_progress',
                        'task_id': task_id,
                        'progress': 20.0,
                        'message': '正在分析您的意图...',
                        'timestamp': datetime.now().isoformat()
                    })

                    result = await scheduler.process(message, **kwargs)

                    await send_sse_message(session_id, {
                        'type': 'task_progress',
                        'task_id': task_id,
                        'progress': 90.0,
                        'message': '处理完成，正在返回结果...',
                        'timestamp': datetime.now().isoformat()
                    })

                    if result.get('success', True):
                        await send_sse_message(session_id, {
                            'type': 'task_status',
                            'task_id': task_id,
                            'status': 'completed',
                            'message': '消息处理完成',
                            'progress': 100,
                            'timestamp': datetime.now().isoformat()
                        })

                        content = result.get('result', {}).get('message') or result.get('message') or '任务已完成'
                        
                        # 直接提取URL（所有生成器现在都返回统一格式的URL字符串）
                        video_path = result.get('result', {}).get('video_path') or result.get('video_path')
                        video_url = result.get('result', {}).get('video_url') or result.get('video_url')
                        image_url = result.get('result', {}).get('image_url') or result.get('image_url')
                        
                        # 确定消息类型
                        message_type = "text"
                        if result.get('intent') == 'generate_image':
                            message_type = "image"
                            # 对于图片消息，content 直接是图片URL，不需要额外的文案
                            content = image_url or video_url or video_path
                        elif video_path or video_url:
                            message_type = "video"
                            # 对于视频消息，content 直接是视频URL，不需要额外的文案
                            content = video_url or video_path

                        await send_sse_message(session_id, {
                            'type': 'assistant_reply',
                            'task_id': task_id,
                            'content': content,
                            'message_type': message_type,
                            'timestamp': datetime.now().isoformat(),
                            'data': { **result, 'session_id': session_id, 'task_id': task_id }
                        })
                    else:
                        # 发送失败状态
                        await send_sse_message(session_id, {
                            'type': 'task_status',
                            'task_id': task_id,
                            'status': 'failed',
                            'message': result.get('error', '处理失败'),
                            'progress': 0,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        # 发送失败的assistant_reply
                        error_message = result.get('message', result.get('error', '处理失败，请稍后重试'))
                        await send_sse_message(session_id, {
                            'type': 'assistant_reply',
                            'task_id': task_id,
                            'content': error_message,
                            'message_type': 'text',
                            'timestamp': datetime.now().isoformat(),
                            'data': { **result, 'session_id': session_id, 'task_id': task_id }
                        })
                except Exception as e:
                    await send_sse_message(session_id, {
                        'type': 'task_status',
                        'task_id': task_id,
                        'status': 'failed',
                        'message': str(e),
                        'progress': 0,
                        'timestamp': datetime.now().isoformat()
                    })

            asyncio.create_task(process_task())

            # 消费并转发该 session 的队列消息
            while True:
                try:
                    msg = await asyncio.wait_for(connection_queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                    # 仅在收到最终助手回复或失败时结束流
                    if (msg.get('type') == 'assistant_reply') or (msg.get('type') == 'task_status' and msg.get('status') == 'failed'):
                        break
                except asyncio.TimeoutError:
                    # 心跳
                    yield f"data: {json.dumps({'type': 'ping', 'timestamp': datetime.now().isoformat()})}\n\n"
        finally:
            unregister_connection(session_id, connection_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


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


@router.get("/sessions")
async def get_all_sessions():
    """
    获取所有会话列表
    
    Returns:
        {
            "success": bool,
            "sessions": [{"session_id": str, "title": str, "last_activity": float, "message_count": int}, ...],
            "error": str
        }
    """
    logger.info("API 调用: /api/chat/sessions")
    
    try:
        from pathlib import Path
        import json
        from agent.context.manager import DEFAULT_DATA_DIR
        
        sessions = []
        
        # 遍历所有会话目录
        if DEFAULT_DATA_DIR.exists():
            for session_dir in DEFAULT_DATA_DIR.iterdir():
                if session_dir.is_dir():
                    session_id = session_dir.name
                    
                    # 读取元数据
                    metadata_path = session_dir / "metadata.json"
                    metadata = {}
                    if metadata_path.exists():
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                    
                    # 读取向量存储获取消息数量和最后活动时间
                    vector_store_path = session_dir / "vector_store.json"
                    message_count = 0
                    last_activity = 0
                    title = "新对话"
                    
                    if vector_store_path.exists():
                        with open(vector_store_path, 'r', encoding='utf-8') as f:
                            vector_data = json.load(f)
                        
                        message_count = len(vector_data.get("items", []))
                        
                        # 找到最后一条消息的时间戳
                        for item in vector_data.get("items", []):
                            item_metadata = item.get("metadata", {})
                            timestamp = item_metadata.get("timestamp", 0)
                            if timestamp > last_activity:
                                last_activity = timestamp
                                # 如果有标题，使用标题
                                if item_metadata.get("title"):
                                    title = item_metadata.get("title")
                    
                    sessions.append({
                        "session_id": session_id,
                        "title": title,
                        "last_activity": last_activity,
                        "message_count": message_count,
                        "metadata": metadata
                    })
        
        # 按最后活动时间排序（最新的在前）
        sessions.sort(key=lambda x: x["last_activity"], reverse=True)
        
        logger.info(f"获取到 {len(sessions)} 个会话")
        
        return {
            "success": True,
            "sessions": sessions
        }
        
    except Exception as e:
        logger.exception(f"获取会话列表出错: {e}")
        return {
            "success": False,
            "sessions": [],
            "error": str(e)
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
                        
                        # 兼容性处理：如果没有message_type，根据intent推断
                        message_type = item_metadata.get("message_type")
                        if not message_type:
                            intent = item_metadata.get("intent", "")
                            if intent == "generate_image":
                                message_type = "image"
                            elif intent == "generate_video":
                                message_type = "video"
                            else:
                                message_type = "text"
                        
                        messages.append({
                            "role": role,
                            "content": message_content,
                            "timestamp": item_metadata.get("timestamp", 0),
                            "message_type": message_type,  # 确保包含message_type
                            "metadata": item_metadata  # 包含所有metadata，包括title
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

