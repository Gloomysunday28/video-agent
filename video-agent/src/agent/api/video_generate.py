"""
视频生成 API 接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from pathlib import Path
import yaml

from agent.tools.generate import JianyingVideoGenerator, JianyingConfig

router = APIRouter(prefix="/api/video", tags=["视频生成"])


class VideoGenerationRequest(BaseModel):
    """视频生成请求"""
    prompt: str = Field(..., description="视频描述文本")
    aspect_ratio: str = Field(default="16:9", description="宽高比")
    duration: int = Field(default=5, description="时长（秒）", ge=1, le=10)
    resolution: str = Field(default="720p", description="分辨率")
    seed: Optional[int] = Field(default=None, description="随机种子")


class VideoStatusRequest(BaseModel):
    """视频状态查询请求"""
    submit_id: str = Field(..., description="提交ID")


def _load_jianying_config() -> JianyingConfig:
    """加载剪映配置"""
    config_path = Path(__file__).parent.parent / "config" / "index.yml"
    
    if not config_path.exists():
        raise ValueError("配置文件不存在")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    jianying_cfg = config.get("jianyingAPI", {})
    
    if not jianying_cfg:
        raise ValueError("剪映API未配置")
    
    return JianyingConfig(
        web_id=jianying_cfg.get("webId", ""),
        ms_token=jianying_cfg.get("msToken", ""),
        generate_sign=jianying_cfg.get("generateSign", ""),
        status_sign=jianying_cfg.get("statusSign", ""),
        generate_a_bogus=jianying_cfg.get("generateABogus", ""),
        status_a_bogus=jianying_cfg.get("statusABogus", ""),
        cookies=jianying_cfg.get("cookies", {})
    )


@router.post("/generate")
async def generate_video(request: VideoGenerationRequest):
    """
    生成视频
    
    - **prompt**: 视频描述文本
    - **aspect_ratio**: 宽高比 (16:9, 9:16等)
    - **duration**: 时长（秒）
    - **resolution**: 分辨率 (720p, 1080p)
    - **seed**: 随机种子（可选）
    """
    try:
        # 加载配置
        config = _load_jianying_config()
        
        # 创建生成器
        generator = JianyingVideoGenerator(config)
        
        # 生成视频
        result = await generator.generate_video(
            prompt=request.prompt,
            aspect_ratio=request.aspect_ratio,
            duration=request.duration,
            resolution=request.resolution,
            seed=request.seed
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/status")
async def get_video_status(request: VideoStatusRequest):
    """
    查询视频生成状态
    
    - **submit_id**: 视频生成提交ID
    """
    try:
        # 加载配置
        config = _load_jianying_config()
        
        # 创建生成器
        generator = JianyingVideoGenerator(config)
        
        # 查询状态
        result = await generator.get_video_status(request.submit_id)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "video-generation",
        "backend": "jianying-cloud-api",
        "version": "1.0.0"
    }

