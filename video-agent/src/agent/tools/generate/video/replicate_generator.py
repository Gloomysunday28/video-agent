"""
Replicate 视频生成器
通过 Replicate API 调用社区模型生成视频
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import os
import httpx
import uuid


@dataclass
class ReplicateConfig:
    api_token: str
    model_owner: str
    model_name: str
    version: Optional[str] = None  # 可选：固定版本；也可在请求时传入


class ReplicateVideoGenerator:
    def __init__(self, config: ReplicateConfig):
        self.config = config
        if not self.config.api_token:
            # 允许从环境变量读取
            self.config.api_token = os.getenv("REPLICATE_API_TOKEN", "")
        if not self.config.api_token:
            raise ValueError("缺少 REPLICATE_API_TOKEN")

    async def generate_video(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        duration: int = 5,
        resolution: str = "720p",
        seed: Optional[int] = None,
        replicate_version: Optional[str] = None,
        extra_input: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        触发 Replicate 推理任务
        返回 prediction id，可用于后续轮询
        """
        # 将常见参数映射为模型通用入参（不同模型可能命名不同，使用 extra_input 覆盖）
        input_payload: Dict[str, Any] = {
            "prompt": prompt,
        }

        if seed is not None:
            input_payload.setdefault("seed", seed)

        # 常见分辨率映射
        res_map = {"720p": (1280, 720), "1080p": (1920, 1080)}
        if resolution in res_map:
            w, h = res_map[resolution]
            input_payload.setdefault("width", w)
            input_payload.setdefault("height", h)

        # 时长/帧数（不同模型习惯不同，这里仅提供占位，具体由 extra_input 覆盖）
        if duration:
            input_payload.setdefault("duration", duration)

        if extra_input:
            input_payload.update(extra_input)

        headers = {
            "Authorization": f"Bearer {self.config.api_token}",
            "Content-Type": "application/json",
        }

        url = "https://api.replicate.com/v1/predictions"

        model_identifier = f"{self.config.model_owner}/{self.config.model_name}"
        version = replicate_version or self.config.version

        body: Dict[str, Any] = {
            "model": model_identifier,
            "input": input_payload,
        }
        if version:
            body["version"] = version

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=headers, json=body)
                if resp.status_code not in (200, 201):
                    return {
                        "success": False,
                        "message": f"Replicate API 错误: {resp.status_code}",
                        "error": resp.text,
                    }
                data = resp.json()
                return {
                    "success": True,
                    "submit_id": data.get("id", str(uuid.uuid4())),
                    "message": "视频生成任务已提交(Replicate)",
                    "raw_response": data,
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"请求失败: {str(e)}",
                "error": str(e),
            }

    async def get_video_status(self, prediction_id: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.config.api_token}",
        }
        url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return {
                        "success": False,
                        "message": f"状态查询错误: {resp.status_code}",
                        "error": resp.text,
                    }
                data = resp.json()
                status = data.get("status", "unknown")
                # Replicate 输出位置通常在 data["output"]（可能是 URL 或列表）
                return {
                    "success": True,
                    "status": status,
                    "output": data.get("output"),
                    "raw_response": data,
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"请求失败: {str(e)}",
                "error": str(e),
            }


