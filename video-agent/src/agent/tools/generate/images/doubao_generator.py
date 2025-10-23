"""
豆包API视频生成器
使用字节跳动的豆包API进行视频生成
"""

import asyncio
import aiohttp
import json
import uuid
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class DoubaoConfig:
    """豆包API配置"""
    api_key: str  # 豆包API Key
    model: str = "doubao-seedream-4-0-250828"  # 豆包图片生成模型ID
    timeout: int = 300  # 请求超时时间（秒）


class DoubaoVideoGenerator:
    """
    豆包API视频生成器
    使用字节跳动的豆包API进行视频生成
    """
    
    def __init__(self, config: DoubaoConfig):
        """
        初始化生成器
        
        Args:
            config: 豆包API配置
        """
        self.config = config
        if not self.config.api_key:
            # 允许从环境变量读取
            self.config.api_key = os.getenv("DOUBAO_API_KEY", "")
        if not self.config.api_key:
            raise ValueError("缺少 DOUBAO_API_KEY")
    
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
        生成图片 - 支持多模态（基于参考图片生成）
        
        Args:
            prompt: 图片描述文本
            aspect_ratio: 宽高比 (16:9, 9:16等) - 豆包不支持此参数
            duration: 时长（秒） - 豆包不支持此参数
            resolution: 分辨率 (720p, 1080p, 2K, 4K)
            seed: 随机种子（可选）
            reference_image: 参考图片URL或base64（用于多模态生成）
            **kwargs: 其他参数
        
        Returns:
            {
                "success": bool,
                "submit_id": str,      # 提交ID
                "message": str,
                "video_path": str,     # 生成的图片URL
                "raw_response": dict
            }
        """
        submit_id = str(uuid.uuid4())
        
        try:
            # 完全按照curl命令构建请求
            size_mapping = {
                "720p": "1k",
                "1080p": "2k", 
                "2K": "2k",
                "4K": "4k"
            }
            api_size = size_mapping.get(resolution, "2k")
            
            request_data = {
                "model": self.config.model,
                "prompt": prompt,
                "size": api_size,
                "sequential_image_generation": "disabled",
                "stream": False,
                "response_format": "url",
                "watermark": True
            }
            
            # 添加可选参数
            if seed is not None:
                request_data["seed"] = seed
            
            # 添加参考图片（多模态）
            if reference_image:
                print(f"[豆包生成器] 接收到的reference_image: {reference_image[:100] if reference_image else None}")
                if reference_image.startswith('http'):
                    # 直接使用URL
                    request_data["image"] = reference_image
                    print(f"[豆包生成器] 使用URL格式: {reference_image}")
                else:
                    # base64格式，豆包API支持data:image/格式
                    if reference_image.startswith('data:image/'):
                        # 已经是正确格式，直接使用
                        request_data["image"] = reference_image
                        print(f"[豆包生成器] 使用已有data:image格式: {reference_image[:50]}...")
                    else:
                        # 纯base64，需要添加data:image/jpeg;base64,前缀
                        request_data["image"] = f"data:image/jpeg;base64,{reference_image}"
                        print(f"[豆包生成器] 添加data:image前缀: {request_data['image'][:50]}...")
                
                print(f"[豆包生成器] 最终传给API的image参数长度: {len(request_data['image'])}")
            
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
            
            url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.config.timeout)) as session:
                async with session.post(url, headers=headers, json=request_data) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        
                        # 处理成功响应
                        if "data" in response_data and len(response_data.get("data", [])) > 0:
                            content_data = response_data["data"][0]
                            content_url = content_data.get("url", "")
                            content_size = content_data.get("size", "")
                            
                            print(f"[豆包生成器] 提取的URL: {content_url}")
                            
                            result = {
                                "success": True,
                                "submit_id": submit_id,
                                "task_id": submit_id,  # 添加task_id字段，与BetterYeah保持一致
                                "message": f"图片生成成功！",
                                "video_path": content_url,  # 保持兼容性
                                "video_url": content_url,   # 保持兼容性
                                "image_url": content_url,   # 图片URL字段
                                "video_size": content_size,
                                "raw_response": response_data
                            }
                            print(f"[豆包生成器] 返回结果: {result}")
                            return result
                        else:
                            return {
                                "success": False,
                                "submit_id": submit_id,
                                "message": "API返回数据格式错误",
                                "error": "API返回数据格式错误",
                                "raw_response": response_data
                            }
                    else:
                        # 处理错误响应
                        try:
                            response_data = await response.json()
                            error_msg = response_data.get("message", f"API请求失败: {response.status}")
                        except:
                            error_msg = f"API请求失败: {response.status}"
                        
                        return {
                            "success": False,
                            "submit_id": submit_id,
                            "message": error_msg,
                            "error": error_msg,
                            "raw_response": {"status": response.status, "text": await response.text()}
                        }
                        
        except asyncio.TimeoutError:
            return {
                "success": False,
                "submit_id": submit_id,
                "message": f"请求超时 ({self.config.timeout}秒)",
                "error": "请求超时",
                "raw_response": {"timeout": self.config.timeout}
            }
        except Exception as e:
            return {
                "success": False,
                "submit_id": submit_id,
                "message": f"豆包API调用失败: {str(e)}",
                "error": str(e),
                "raw_response": {"exception": str(e)}
            }
    
    async def get_video_status(self, submit_id: str) -> Dict[str, Any]:
        """
        查询视频生成状态 - 豆包图片生成是同步的，不需要状态查询
        
        Args:
            submit_id: 提交ID
        
        Returns:
            {
                "success": bool,
                "status": str,         # completed
                "message": str,
                "video_url": str,      # 图片URL
                "raw_response": dict
            }
        """
        # 豆包图片生成是同步的，直接返回完成状态
        return {
            "success": True,
            "status": "completed",
            "message": "豆包图片生成是同步的，无需状态查询",
            "raw_response": {
                "note": "豆包图片生成API是同步的，生成完成后直接返回结果"
            }
        }


# 使用示例
if __name__ == "__main__":
    import asyncio
    
    async def test():
        # 配置豆包生成器
        config = DoubaoConfig(
            api_key="your_doubao_api_key_here",
            model="doubao-video-001"
        )
        
        generator = DoubaoVideoGenerator(config)
        
        # 生成视频
        print("开始生成视频...")
        result = await generator.generate_video(
            prompt="一只可爱的小猫在草地上玩耍",
            aspect_ratio="16:9",
            duration=5,
            resolution="720p"
        )
        
        print(f"生成结果: {result}")
        
        # 查询状态
        if result.get("submit_id"):
            print("查询视频状态...")
            status_result = await generator.get_video_status(result["submit_id"])
            print(f"状态查询结果: {status_result}")
    
    asyncio.run(test())
