"""
视频生成 API 接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from agent.tools.generate import JianyingVideoGenerator, JianyingConfig, ScriptVideoGenerator, ScriptConfig, ReplicateVideoGenerator, ReplicateConfig, DoubaoVideoGenerator, DoubaoConfig
import os
from agent.api.common import (
    generate_session_id,
    execute_with_scheduler,
    load_jianying_config,
    load_doubao_config,
    handle_api_error
)
from agent.api.sse import send_task_status, send_task_progress, send_task_error, send_task_completed
import uuid
import asyncio

router = APIRouter(prefix="/api/video/generate", tags=["视频生成"])


class VideoGenerationRequest(BaseModel):
    """视频生成请求"""
    session_id: str = Field(default_factory=generate_session_id, description="会话ID")
    prompt: str = Field(..., description="视频描述文本")
    aspect_ratio: str = Field(default="16:9", description="宽高比")
    duration: int = Field(default=5, description="时长（秒）", ge=1, le=10)
    resolution: str = Field(default="720p", description="分辨率")
    seed: Optional[int] = Field(default=None, description="随机种子")
    generator_type: str = Field(default="jianying", description="生成器类型: jianying(剪映API)、doubao(豆包API)、replicate(Replicate) 或 script(脚本调用)")
    script_path: Optional[str] = Field(default=None, description="脚本路径（当generator_type为script时必填）")
    timeout: Optional[int] = Field(default=900, description="超时时间（秒），仅脚本生成器")
    # 以下为可选透传参数（用于复用浏览器抓包得到的易失效签名/头）
    override_sign: Optional[str] = Field(default=None, description="生成接口的 sign")
    override_a_bogus: Optional[str] = Field(default=None, description="生成接口的 a_bogus")
    override_ms_token: Optional[str] = Field(default=None, description="生成接口的 msToken")
    override_device_time: Optional[str] = Field(default=None, description="请求头 device-time")
    # Replicate 可选参数
    replicate_model_owner: Optional[str] = Field(default=None, description="Replicate 模型 owner")
    replicate_model_name: Optional[str] = Field(default=None, description="Replicate 模型 name")
    replicate_api_token: Optional[str] = Field(default=None, description="Replicate API Token（直传，优先于环境变量）")
    replicate_version: Optional[str] = Field(default=None, description="Replicate 模型版本（可选）")
    # 豆包 可选参数
    doubao_api_key: Optional[str] = Field(default=None, description="豆包 API Key（直传，优先于环境变量）")
    doubao_model: Optional[str] = Field(default=None, description="豆包模型名称（可选）")


class VideoStatusRequest(BaseModel):
    """视频状态查询请求"""
    submit_id: str = Field(..., description="提交ID")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    generator_type: Optional[str] = Field(default="jianying", description="生成器类型: jianying、doubao 或 replicate")
    replicate_model_owner: Optional[str] = Field(default=None, description="Replicate 模型 owner")
    replicate_model_name: Optional[str] = Field(default=None, description="Replicate 模型 name")
    # 豆包参数
    doubao_api_key: Optional[str] = Field(default=None, description="豆包 API Key")


@router.post("/")
async def generate_video(request: VideoGenerationRequest):
    """
    生成视频（支持WebSocket状态推送）
    
    - **session_id**: 会话ID（自动生成或指定）
    - **prompt**: 视频描述文本
    - **aspect_ratio**: 宽高比 (16:9, 9:16等)
    - **duration**: 时长（秒）
    - **resolution**: 分辨率 (720p, 1080p)
    - **seed**: 随机种子（可选）
    - **generator_type**: 生成器类型 (jianying/script)
    - **script_path**: 脚本路径（当generator_type为script时必填）
    """
    task_id = str(uuid.uuid4())
    
    try:
        # 发送任务开始状态
        await send_task_status(
            request.session_id, 
            task_id, 
            "pending", 
            "视频生成任务已开始，正在初始化..."
        )
        
        if request.generator_type == "script":
            # 使用脚本生成器
            if not request.script_path:
                await send_task_error(
                    request.session_id,
                    task_id,
                    "使用脚本生成器时必须提供script_path参数"
                )
                raise ValueError("使用脚本生成器时必须提供script_path参数")
            
            await send_task_progress(
                request.session_id,
                task_id,
                10.0,
                "正在配置脚本生成器..."
            )
            
            config = ScriptConfig(
                script_path=request.script_path,
                python_executable="python3",
                timeout=request.timeout or 900
            )
            generator = ScriptVideoGenerator(config)
            
            await send_task_progress(
                request.session_id,
                task_id,
                20.0,
                "开始执行视频生成脚本..."
            )
        elif request.generator_type == "replicate":
            await send_task_progress(
                request.session_id,
                task_id,
                10.0,
                "正在配置 Replicate..."
            )
         
            if not hasattr(request, "replicate_model_owner") or not hasattr(request, "replicate_model_name"):
                raise ValueError("缺少 replicate 模型标识：owner/name")
            r_config = ReplicateConfig(
                api_token=token,
                model_owner=getattr(request, "replicate_model_owner", ""),
                model_name=getattr(request, "replicate_model_name", ""),
            )
            generator = ReplicateVideoGenerator(r_config)
            await send_task_progress(
                request.session_id,
                task_id,
                20.0,
                "开始调用 Replicate 生成视频..."
            )
        elif request.generator_type == "replicate":
            await send_task_progress(
                request.session_id,
                task_id,
                10.0,
                "正在配置 Replicate..."
            )
            token = request.replicate_api_token or os.getenv("REPLICATE_API_TOKEN", "")
            if not token:
                raise ValueError("缺少 Replicate Token（replicate_api_token 或 REPLICATE_API_TOKEN）")
            if not request.replicate_model_owner or not request.replicate_model_name:
                raise ValueError("缺少 replicate 模型标识：owner/name")
            r_config = ReplicateConfig(
                api_token=token,
                model_owner=request.replicate_model_owner,
                model_name=request.replicate_model_name,
                version=request.replicate_version
            )
            generator = ReplicateVideoGenerator(r_config)
            await send_task_progress(
                request.session_id,
                task_id,
                20.0,
                "开始调用 Replicate 生成视频..."
            )
        elif request.generator_type == "doubao":
            await send_task_progress(
                request.session_id,
                task_id,
                10.0,
                "正在配置豆包API..."
            )
            
            # 优先使用请求中的API密钥，否则从配置文件加载
            if request.doubao_api_key:
                config = DoubaoConfig(
                    api_key=request.doubao_api_key,
                    model=request.doubao_model or "doubao-seed-1-6-251015"
                )
            else:
                config = load_doubao_config()
                if request.doubao_model:
                    config.model = request.doubao_model
            
            generator = DoubaoVideoGenerator(config)
            
            await send_task_progress(
                request.session_id,
                task_id,
                20.0,
                "开始调用豆包API生成视频..."
            )
        else:
            # 使用剪映生成器（默认）
            await send_task_progress(
                request.session_id,
                task_id,
                10.0,
                "正在配置剪映API..."
            )
            
            config = load_jianying_config()
            generator = JianyingVideoGenerator(config)
            
            await send_task_progress(
                request.session_id,
                task_id,
                20.0,
                "开始调用剪映API生成视频..."
            )
        
        # 发送处理中状态
        await send_task_status(
            request.session_id,
            task_id,
            "processing",
            "正在生成视频，请稍候..."
        )
        
        # 调用生成（这里可以添加进度回调）
        result = await generator.generate_video(
            prompt=request.prompt,
            aspect_ratio=request.aspect_ratio,
            duration=request.duration,
            resolution=request.resolution,
            seed=request.seed,
            override_sign=request.override_sign,
            override_a_bogus=request.override_a_bogus,
            override_ms_token=request.override_ms_token,
            override_device_time=request.override_device_time
        )
        
        # 添加会话ID和任务ID
        result["session_id"] = request.session_id
        result["task_id"] = task_id
        
        # 豆包生成器是同步的，直接返回结果
        if request.generator_type == "doubao":
            if result.get("success"):
                await send_task_completed(
                    request.session_id,
                    task_id,
                    result.get("message", "图片生成成功！"),
                    result
                )
            else:
                await send_task_error(
                    request.session_id,
                    task_id,
                    result.get("message", "图片生成失败"),
                    result
                )
        else:
            # 其他生成器需要轮询状态
            if result.get("success"):
                await send_task_progress(
                    request.session_id,
                    task_id,
                    90.0,
                    "视频生成完成，正在处理结果..."
                )
                
                await send_task_completed(
                    request.session_id,
                    task_id,
                    result.get("message", "视频生成成功！"),
                    result
                )
            else:
                await send_task_error(
                    request.session_id,
                    task_id,
                    result.get("message", "视频生成失败"),
                    result
                )
        
        return result
        
    except Exception as e:
        error_msg = f"视频生成失败: {str(e)}"
        await send_task_error(
            request.session_id,
            task_id,
            error_msg,
            {"exception": str(e)}
        )
        raise handle_api_error(e)


@router.post("/status")
async def get_video_status(request: VideoStatusRequest):
    """
    查询视频生成状态
    
    - **submit_id**: 视频生成提交ID
    - **session_id**: 会话ID（可选）
    """
    try:
        if request.generator_type == "replicate":
            token = os.getenv("REPLICATE_API_TOKEN", "")
            if not token:
                raise ValueError("缺少 REPLICATE_API_TOKEN")
            if not request.replicate_model_owner or not request.replicate_model_name:
                raise ValueError("缺少 replicate 模型标识：owner/name")
            r_config = ReplicateConfig(
                api_token=token,
                model_owner=request.replicate_model_owner,
                model_name=request.replicate_model_name,
            )
            generator = ReplicateVideoGenerator(r_config)
            result = await generator.get_video_status(request.submit_id)
        elif request.generator_type == "doubao":
            # 豆包状态查询
            if request.doubao_api_key:
                config = DoubaoConfig(api_key=request.doubao_api_key)
            else:
                config = load_doubao_config()
            generator = DoubaoVideoGenerator(config)
            result = await generator.get_video_status(request.submit_id)
        else:
            # 剪映状态查询
            config = load_jianying_config()
            generator = JianyingVideoGenerator(config)
            result = await generator.get_video_status(request.submit_id)
        
        # 添加会话ID（如果提供）
        if request.session_id:
            result["session_id"] = request.session_id
        
        return result
        
    except Exception as e:
        raise handle_api_error(e)



