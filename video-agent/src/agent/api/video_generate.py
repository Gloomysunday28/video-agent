"""
视频生成 API 接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from agent.tools.generate import JianyingVideoGenerator
from agent.api.common import (
    generate_session_id,
    execute_with_scheduler,
    load_jianying_config,
    handle_api_error
)

router = APIRouter(prefix="/api/video/generate", tags=["视频生成"])


class VideoGenerationRequest(BaseModel):
    """视频生成请求"""
    session_id: str = Field(default_factory=generate_session_id, description="会话ID")
    prompt: str = Field(..., description="视频描述文本")
    aspect_ratio: str = Field(default="16:9", description="宽高比")
    duration: int = Field(default=5, description="时长（秒）", ge=1, le=10)
    resolution: str = Field(default="720p", description="分辨率")
    seed: Optional[int] = Field(default=None, description="随机种子")


class VideoStatusRequest(BaseModel):
    """视频状态查询请求"""
    submit_id: str = Field(..., description="提交ID")
    session_id: Optional[str] = Field(default=None, description="会话ID")


@router.post("/")
async def generate_video(request: VideoGenerationRequest):
    """
    生成视频
    
    - **session_id**: 会话ID（自动生成或指定）
    - **prompt**: 视频描述文本
    - **aspect_ratio**: 宽高比 (16:9, 9:16等)
    - **duration**: 时长（秒）
    - **resolution**: 分辨率 (720p, 1080p)
    - **seed**: 随机种子（可选）
    """
    try:
        # 直接使用视频生成工具
        config = load_jianying_config()
        generator = JianyingVideoGenerator(config)
        
        # 调用生成
        result = await generator.generate_video(
            prompt=request.prompt,
            aspect_ratio=request.aspect_ratio,
            duration=request.duration,
            resolution=request.resolution,
            seed=request.seed
        )
        
        # 添加会话ID
        result["session_id"] = request.session_id
        
        return result
        
    except Exception as e:
        raise handle_api_error(e)


@router.post("/status")
async def get_video_status(request: VideoStatusRequest):
    """
    查询视频生成状态
    
    - **submit_id**: 视频生成提交ID
    - **session_id**: 会话ID（可选）
    """
    try:
        # 加载配置
        config = load_jianying_config()
        
        # 创建生成器
        generator = JianyingVideoGenerator(config)
        
        # 查询状态
        result = await generator.get_video_status(request.submit_id)
        
        # 添加会话ID（如果提供）
        if request.session_id:
            result["session_id"] = request.session_id
        
        return result
        
    except Exception as e:
        raise handle_api_error(e)



