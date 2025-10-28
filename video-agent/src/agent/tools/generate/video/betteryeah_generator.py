"""
图生视频生成器 - BetterYeah API
"""

import httpx
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ImageToVideoConfig:
    """图生视频配置"""
    api_url: str
    access_key: str
    workspace_id: str
    max_poll_attempts: int = 60  # 最多轮询次数
    poll_interval: int = 5  # 轮询间隔(秒)


class ImageToVideoGenerator:
    """图生视频生成器"""
    
    def __init__(self, config: ImageToVideoConfig):
        """
        初始化生成器
        
        Args:
            config: 配置对象
        """
        self.config = config
        # 图生视频API需要更长的超时时间
        # connect: 连接超时, read: 读取超时, write: 写入超时, pool: 连接池超时
        timeout = httpx.Timeout(
            connect=30.0,    # 连接超时 30秒
            read=300.0,      # 读取超时 300秒（5分钟，API处理图片需要很长时间）
            write=120.0,     # 写入超时 120秒（上传大图片需要时间）
            pool=30.0        # 连接池超时 30秒
        )
        # 禁用代理，避免网络问题
        self.client = httpx.AsyncClient(
            timeout=timeout,
            trust_env=False,  # 禁用系统代理设置
            follow_redirects=True  # 允许跟随重定向
        )
    
    async def generate_video(
        self,
        prompt: str,
        image_url: str,
        session_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成视频（图生视频）
        
        Args:
            prompt: 用户描述
            image_url: 图片URL或base64
            **kwargs: 其他参数
        
        Returns:
            生成结果
        """
        try:
            print(f"[图生视频生成器] 开始生成视频")
            print(f"[图生视频生成器] Prompt: {prompt}")
            
            # 检查image_url是HTTP URL还是base64
            is_http_url = image_url.startswith('http://') or image_url.startswith('https://')
            
            if not is_http_url:
                print(f"[图生视频生成器] ✗ 错误：API只接受HTTP图片URL，不支持base64数据")
                print(f"[图生视频生成器] 提示：请在对话中直接提供图片的HTTP URL")
                return {
                    "success": False,
                    "message": "图生视频API需要HTTP图片URL，不支持base64数据。请提供图片的URL链接。"
                }
            
            print(f"[图生视频生成器] 图片URL: {image_url}")
            
            # 1. 调用生成接口
            headers = {
                "Content-Type": "application/json",
                "Access-Key": self.config.access_key,
                "Workspace-Id": self.config.workspace_id
            }
            
            request_data = {
                "inputs": {
                    "message": prompt,
                    "file": image_url
                }
            }
            
            print(f"[图生视频生成器] ========== 开始发送请求 ==========")
            print(f"[图生视频生成器] 目标URL: {self.config.api_url}")
            print(f"[图生视频生成器] Headers: Access-Key={self.config.access_key[:20]}..., Workspace-Id={self.config.workspace_id}")
            print(f"[图生视频生成器] 图片URL: {image_url}")
            print(f"[图生视频生成器] Prompt: {prompt}")
            print(f"[图生视频生成器] 正在提交任务，请耐心等待（最长5分钟）...")
            
            # 推送进度提示
            if session_id:
                try:
                    from agent.api.sse import send_sse_message
                    from datetime import datetime
                    await send_sse_message(session_id, {
                        "type": "task_progress",
                        "task_id": "image_to_video_submit",
                        "progress": 10,
                        "message": "正在上传图片并提交任务，请稍候...",
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as e:
                    print(f"[图生视频生成器] SSE推送失败: {e}")
            
            print(f"[图生视频生成器] >>> 正在发送POST请求...")
            import time
            start_time = time.time()
            
            try:
                response = await self.client.post(
                    self.config.api_url,
                    headers=headers,
                    json=request_data
                )
                elapsed = time.time() - start_time
                print(f"[图生视频生成器] >>> 请求完成，耗时: {elapsed:.2f}秒")
            except httpx.ConnectTimeout as e:
                elapsed = time.time() - start_time
                print(f"[图生视频生成器] ✗ 连接超时！耗时: {elapsed:.2f}秒")
                print(f"[图生视频生成器] 错误详情: {e}")
                raise
            except httpx.ReadTimeout as e:
                elapsed = time.time() - start_time
                print(f"[图生视频生成器] ✗ 读取超时！耗时: {elapsed:.2f}秒")
                print(f"[图生视频生成器] 这意味着请求已发送，但服务器响应超时")
                print(f"[图生视频生成器] 错误详情: {e}")
                raise
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"[图生视频生成器] ✗ 其他错误！耗时: {elapsed:.2f}秒")
                print(f"[图生视频生成器] 错误类型: {type(e).__name__}")
                print(f"[图生视频生成器] 错误详情: {e}")
                raise
            
            print(f"[图生视频生成器] ✓ 任务提交成功！API响应状态码: {response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text
                print(f"[图生视频生成器] API请求失败，状态码: {response.status_code}, 响应: {error_text[:500]}")
                return {
                    "success": False,
                    "message": f"API请求失败: {response.status_code}",
                    "error": error_text
                }
            
            response_data = response.json()
            print(f"[图生视频生成器] 初始响应: {response_data}")
            
            # 2. 获取轮询URL（从data.run_result字段提取）
            # 响应格式: {"code": 200, "success": True, "data": {"status": "SUCCEEDED", "run_result": "https://..."}}
            status_url = None
            if isinstance(response_data, dict):
                # 检查是否有错误
                if response_data.get("success") is False:
                    error_msg = response_data.get("message", "未知错误")
                    print(f"[图生视频生成器] API返回错误: {error_msg}")
                    return {
                        "success": False,
                        "message": f"API返回错误: {error_msg}",
                        "raw_response": response_data
                    }
                
                # 从 data.run_result 提取轮询URL
                data = response_data.get("data", {})
                if isinstance(data, dict):
                    status_url = data.get("run_result")
                    print(f"[图生视频生成器] ✓ 获取到轮询URL: {status_url}")
            
            if not status_url or not isinstance(status_url, str):
                print(f"[图生视频生成器] ✗ 未返回有效的状态查询URL")
                print(f"[图生视频生成器] 完整响应: {response_data}")
                return {
                    "success": False,
                    "message": "未返回状态查询URL",
                    "raw_response": response_data
                }
            
            print(f"[图生视频生成器] 开始轮询状态: {status_url}")
            
            # 3. 轮询状态
            for attempt in range(self.config.max_poll_attempts):
                await asyncio.sleep(self.config.poll_interval)
                
                status_response = await self.client.get(status_url)
                
                if status_response.status_code != 200:
                    print(f"[图生视频生成器] 状态查询失败: {status_response.status_code}")
                    continue
                
                status_data = status_response.json()
                print(f"[图生视频生成器] 轮询 {attempt + 1}/{self.config.max_poll_attempts}: {status_data.get('message', 'processing')}")
                
                # 推送进度到前端
                if session_id:
                    try:
                        from agent.api.sse import send_task_progress
                        progress = int((attempt + 1) / self.config.max_poll_attempts * 100)
                        await send_task_progress(
                            session_id=session_id,
                            task_id="image_to_video",
                            progress=progress,
                            message=f"正在生成视频...({attempt + 1}/{self.config.max_poll_attempts})"
                        )
                    except Exception as e:
                        print(f"[图生视频生成器] SSE推送失败: {e}")
                
                # 检查是否成功
                # 成功响应格式: {"code": 200, "success": true, "message": "SUCCESS", "data": "https://xxx.mp4", ...}
                if status_data.get("success") and status_data.get("code") == 200:
                    # 从data字段提取视频URL
                    video_url = status_data.get("data")
                    if video_url and isinstance(video_url, str) and (video_url.startswith("http://") or video_url.startswith("https://")):
                        print(f"[图生视频生成器] ✓ 视频生成成功: {video_url}")
                        return {
                            "success": True,
                            "message": "视频生成成功！",
                            "video_url": video_url,
                            "video_path": video_url,
                            "task_id": status_data.get("request_id"),
                            "raw_response": status_data
                        }
                
                # 检查是否失败
                if status_data.get("success") is False:
                    return {
                        "success": False,
                        "message": f"视频生成失败: {status_data.get('message', 'Unknown error')}",
                        "raw_response": status_data
                    }
            
            # 超时
            return {
                "success": False,
                "message": f"视频生成超时（超过{self.config.max_poll_attempts * self.config.poll_interval}秒）",
            }
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[图生视频生成器] ✗ 生成失败: {e}")
            print(f"[图生视频生成器] 详细错误: {error_detail}")
            return {
                "success": False,
                "message": f"视频生成失败: {str(e) if str(e) else '未知错误'}",
                "error": str(e),
                "error_detail": error_detail
            }
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

