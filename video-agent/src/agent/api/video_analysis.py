"""
视频识别/分析 API 接口
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field
from typing import Optional
import os
import tempfile
import logging

from agent.api.common import (
    generate_session_id,
    execute_with_scheduler,
    handle_api_error
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/video/analysis", tags=["视频识别"])


class VideoAnalysisRequest(BaseModel):
    """视频分析请求"""
    session_id: str = Field(default_factory=generate_session_id, description="会话ID")
    video_url: Optional[str] = Field(default=None, description="视频URL")
    task: str = Field(default="describe", description="分析任务类型 (describe/action/scene/emotion/object/summary/quality/transcription)")
    custom_prompt: Optional[str] = Field(default=None, description="自定义提示词")


@router.post("/")
async def analyze_video(request: VideoAnalysisRequest):
    """
    分析视频内容
    
    - **session_id**: 会话ID（自动生成或指定）
    - **video_url**: 视频URL（必填）
    - **task**: 分析任务类型
      - `describe`: 详细描述视频内容
      - `action`: 识别动作和行为
      - `scene`: 分析场景和环境
      - `emotion`: 识别情感和情绪
      - `object`: 识别物体
      - `summary`: 生成视频摘要
      - `quality`: 评估视频质量
      - `transcription`: 转录文字和对话
    - **custom_prompt**: 自定义分析提示词
    """
    logger.info("=" * 80)
    logger.info("API 调用: /api/video/analysis/")
    logger.info(f"入参: {request.model_dump()}")
    
    try:
        if not request.video_url:
            raise ValueError("video_url 不能为空")
        
        # 直接使用视频分析工具，不走意图识别
        from agent.tools.vision import VideoAnalyzer
        
        analyzer = VideoAnalyzer()
        
        # 调用分析
        logger.info(f"调用 analyzer.analyze_video(video_path={request.video_url}, task={request.task}, custom_prompt={request.custom_prompt})")
        
        result = await analyzer.analyze_video(
            video_path=request.video_url,
            task=request.task,
            custom_prompt=request.custom_prompt
        )
        
        logger.info(f"analyzer.analyze_video 返回结果: {result}")
        
        # 添加会话ID
        result["session_id"] = request.session_id
        
        logger.info(f"API 出参: {result}")
        logger.info("=" * 80)
        
        return result
        
    except Exception as e:
        logger.exception(f"API 调用出错: {e}")
        raise handle_api_error(e)


@router.post("/upload")
async def analyze_uploaded_video(
    file: UploadFile = File(...),
    session_id: str = Query(default_factory=generate_session_id),
    task: str = Query(default="describe"),
    custom_prompt: Optional[str] = Query(default=None)
):
    """
    上传并分析视频文件
    
    - **session_id**: 会话ID（自动生成或指定）
    - **task**: 分析任务类型
    - **custom_prompt**: 自定义提示词
    - **file**: 视频文件
    """
    try:
        # 验证文件类型
        if not file.content_type.startswith("video/"):
            raise ValueError(f"不支持的文件类型: {file.content_type}，仅支持视频文件")
        
        # 创建临时文件保存上传的视频
        suffix = os.path.splitext(file.filename)[1] if file.filename else ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            # 写入视频内容
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            # 直接使用视频分析工具
            from agent.tools.vision import VideoAnalyzer
            
            analyzer = VideoAnalyzer()
            
            # 调用分析
            result = await analyzer.analyze_video(
                video_path=temp_path,
                task=task,
                custom_prompt=custom_prompt
            )
            
            # 添加会话ID和文件名
            result["session_id"] = session_id
            result["filename"] = file.filename
            
            return result
            
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_path)
            except:
                pass
        
    except Exception as e:
        raise handle_api_error(e)


@router.get("/tasks")
async def get_available_tasks():
    """
    获取可用的分析任务列表
    """
    return {
        "tasks": [
            {
                "id": "describe",
                "name": "视频描述",
                "description": "详细描述视频的内容、场景、人物和事件"
            },
            {
                "id": "action",
                "name": "动作识别",
                "description": "识别并描述视频中发生的动作和行为"
            },
            {
                "id": "scene",
                "name": "场景分析",
                "description": "分析视频的场景、环境和空间布局"
            },
            {
                "id": "emotion",
                "name": "情感识别",
                "description": "识别视频中表达的情感和情绪"
            },
            {
                "id": "object",
                "name": "物体识别",
                "description": "识别视频中出现的物体"
            },
            {
                "id": "summary",
                "name": "视频摘要",
                "description": "生成简洁的视频摘要"
            },
            {
                "id": "quality",
                "name": "质量评估",
                "description": "评估视频的技术质量"
            },
            {
                "id": "transcription",
                "name": "内容转录",
                "description": "转录视频中的文字和对话"
            }
        ]
    }

