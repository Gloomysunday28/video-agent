"""
BetterYeah API图片生成器
使用BetterYeah的文生图API进行图片生成
"""

import asyncio
import aiohttp
import json
import uuid
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class BetterYeahConfig:
    """BetterYeah API配置"""
    api_url: str  # API完整URL
    access_key: str  # Access Key
    workspace_id: str  # Workspace ID
    timeout: int = 300  # 请求超时时间（秒）


class BetterYeahImageGenerator:
    """
    BetterYeah API图片生成器
    使用BetterYeah的文生图API进行图片生成
    """
    
    def __init__(self, config: BetterYeahConfig):
        """
        初始化生成器
        
        Args:
            config: BetterYeah API配置
        """
        self.config = config
        if not self.config.access_key:
            # 允许从环境变量读取
            self.config.access_key = os.getenv("BETTERYEAH_ACCESS_KEY", "")
        if not self.config.access_key:
            raise ValueError("缺少 BETTERYEAH_ACCESS_KEY")
    
    async def generate_video(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        duration: int = 5,
        resolution: str = "720p",
        seed: Optional[int] = None,
        reference_image: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成图片（保持接口兼容性，实际是图片生成）
        
        Args:
            prompt: 图片描述提示词
            aspect_ratio: 宽高比（忽略）
            duration: 忽略（图片生成不需要时长）
            resolution: 分辨率（忽略）
            seed: 随机种子（忽略）
            reference_image: 参考图片（忽略）
            **kwargs: 其他参数
        
        Returns:
            生成结果字典
        """
        try:
            print(f"[BetterYeah生成器] 开始生成图片，提示词: {prompt}")
            
            # 生成唯一ID
            submit_id = str(uuid.uuid4())
            
            # 构建请求头
            headers = {
                "Content-Type": "application/json",
                "Access-Key": self.config.access_key,
                "Workspace-Id": self.config.workspace_id
            }
            
            # 构建请求数据
            request_data = {
                "inputs": {
                    "message": prompt
                }
            }
            
            print(f"[BetterYeah生成器] 请求参数: {request_data}")
            print(f"[BetterYeah生成器] 请求头: {headers}")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.config.timeout)) as session:
                async with session.post(self.config.api_url, headers=headers, json=request_data) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        
                        # 处理成功响应
                        print(f"[BetterYeah生成器] API响应: {response_data}")
                        
                        if response_data.get("success") and response_data.get("data"):
                            data = response_data["data"]
                            
                            # 检查任务状态
                            if data.get("status") == "SUCCEEDED":
                                # 任务已完成，获取结果
                                run_result = data.get("run_result", "")
                                
                                # 假设run_result包含图片URL或base64
                                if run_result and run_result != "XXXXXXX":
                                    # 提取实际的URL，处理可能的嵌套结构
                                    actual_url = run_result
                                    if isinstance(run_result, dict) and 'message' in run_result:
                                        actual_url = run_result['message']
                                    elif isinstance(run_result, str):
                                        # 尝试解析JSON字符串
                                        try:
                                            import json
                                            parsed = json.loads(run_result)
                                            if isinstance(parsed, dict) and 'message' in parsed:
                                                actual_url = parsed['message']
                                        except:
                                            # 如果解析失败，直接使用原始字符串
                                            actual_url = run_result
                                    
                                    print(f"[BetterYeah生成器] 提取的URL: {actual_url}")
                                    
                                    result = {
                                        "success": True,
                                        "submit_id": submit_id,
                                        "task_id": data.get("task_id", ""),
                                        "message": f"图片生成成功！",
                                        "video_path": actual_url,  # 统一格式：直接返回URL字符串
                                        "video_url": actual_url,   # 统一格式：直接返回URL字符串
                                        "image_url": actual_url,   # 统一格式：直接返回URL字符串
                                        "raw_response": response_data
                                    }
                                    print(f"[BetterYeah生成器] 返回结果: {result}")
                                    return result
                                else:
                                    return {
                                        "success": False,
                                        "submit_id": submit_id,
                                        "message": "图片生成完成但结果为空",
                                        "raw_response": response_data
                                    }
                            else:
                                # 任务还在处理中，返回任务ID用于后续查询
                                return {
                                    "success": True,
                                    "submit_id": data.get("task_id", submit_id),
                                    "task_id": data.get("task_id", ""),
                                    "status": data.get("status", "PROCESSING"),
                                    "message": "图片生成任务已提交，正在处理中...",
                                    "raw_response": response_data
                                }
                        else:
                            return {
                                "success": False,
                                "submit_id": submit_id,
                                "message": "API返回数据格式错误",
                                "raw_response": response_data
                            }
                    else:
                        error_text = await response.text()
                        print(f"[BetterYeah生成器] API调用失败: {response.status} - {error_text}")
                        return {
                            "success": False,
                            "submit_id": submit_id,
                            "message": f"API调用失败: HTTP {response.status}",
                            "error": error_text
                        }
                        
        except asyncio.TimeoutError:
            print(f"[BetterYeah生成器] 请求超时")
            return {
                "success": False,
                "submit_id": submit_id,
                "message": "请求超时，请稍后重试"
            }
        except Exception as e:
            print(f"[BetterYeah生成器] 生成失败: {e}")
            return {
                "success": False,
                "submit_id": submit_id,
                "message": f"生成失败: {str(e)}"
            }
    
    async def get_video_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询图片生成状态（如果需要轮询的话）
        
        Args:
            task_id: 任务ID
            
        Returns:
            状态查询结果
        """
        # 这个API可能不需要轮询，直接返回完成状态
        return {
            "success": True,
            "status": "completed",
            "task_id": task_id
        }


# 使用示例
if __name__ == "__main__":
    async def test():
        config = BetterYeahConfig(
            api_url="https://pre-ai-api.betteryeah.com/v1/public_api/rest_api/44c1bcc473f447748d46bd5f313bfd24/execute_flow",
            access_key="Your-Access-Key",
            workspace_id="652606ad6b292b46387de531"
        )
        
        generator = BetterYeahImageGenerator(config)
        
        result = await generator.generate_video(
            prompt="一只可爱的小猫在花园里玩耍"
        )
        
        print("生成结果:", result)
    
    asyncio.run(test())
