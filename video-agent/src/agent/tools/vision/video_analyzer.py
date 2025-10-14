"""
视频分析器
使用视觉模型分析视频内容
"""

import base64
import httpx
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml


class VideoAnalyzer:
    """
    视频分析器
    支持多种模型的视频/图像识别
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        prompt_path: Optional[str] = None
    ):
        """
        初始化视频分析器
        
        Args:
            config_path: 配置文件路径
            prompt_path: Prompt配置文件路径
        """
        # 加载配置
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "index.yml"
        self.config = self._load_config(config_path)
        
        # 加载Prompt配置
        if prompt_path is None:
            prompt_path = Path(__file__).parent.parent.parent / "prompts" / "vision" / "index.yml"
        self.prompts = self._load_config(prompt_path)
        
        # 获取视觉模型配置
        self.vision_config = self.config.get("visionLLM", {})
        self.api_key = self.vision_config.get("apiKey")
        self.base_url = self.vision_config.get("baseUrl")
        self.model = self.vision_config.get("model", "gemini-2.5-flash")
    
    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """加载配置文件"""
        if not config_path.exists():
            return {}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _is_gemini_model(self) -> bool:
        """判断是否为Gemini模型"""
        return "gemini" in self.model.lower()
    
    def _is_claude_model(self) -> bool:
        """判断是否为Claude模型"""
        return "claude" in self.model.lower()
    
    async def analyze_video(
        self,
        video_path: str,
        task: str = "describe",
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析视频内容
        
        Args:
            video_path: 视频文件路径或URL
            task: 分析任务类型 (describe, action, scene, emotion等)
            custom_prompt: 自定义prompt，如果提供则覆盖默认prompt
        
        Returns:
            {
                "success": bool,
                "result": str,  # 分析结果
                "model": str,   # 使用的模型
                "method": str,  # 分析方法 (native_video, frame_extraction)
                "error": str    # 错误信息（如果有）
            }
        """
        if not self.api_key or not self.base_url:
            return {
                "success": False,
                "error": "视觉模型未配置"
            }
        
        # Gemini模型支持原生视频分析
        if self._is_gemini_model():
            return await self._analyze_video_gemini(video_path, task, custom_prompt)
        else:
            # 其他模型需要拆帧分析
            return await self._analyze_video_with_frames(video_path, task, custom_prompt)
    
    async def _analyze_video_gemini(
        self,
        video_path: str,
        task: str,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """使用Gemini原生视频分析"""
        try:
            # 获取prompt
            if custom_prompt:
                prompt = custom_prompt
            else:
                prompt = self._get_prompt_for_task(task)
            
            # 读取视频文件并编码为base64
            video_data = self._read_video_file(video_path)
            if not video_data:
                return {
                    "success": False,
                    "error": f"无法读取视频文件: {video_path}"
                }
            
            # 构建请求
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": prompt
                                    },
                                    {
                                        "type": "video",
                                        "video": {
                                            "data": video_data,
                                            "format": "base64"
                                        }
                                    }
                                ]
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 1000
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    return {
                        "success": True,
                        "result": content,
                        "model": self.model,
                        "method": "native_video",
                        "task": task
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API错误: {response.status_code} - {response.text}",
                        "model": self.model
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"分析失败: {str(e)}",
                "model": self.model
            }
    
    async def _analyze_video_with_frames(
        self,
        video_path: str,
        task: str,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """通过拆帧分析视频（用于不支持视频的模型）"""
        # TODO: 实现视频拆帧功能
        return {
            "success": False,
            "error": "视频拆帧功能待实现，建议使用Gemini模型",
            "model": self.model,
            "method": "frame_extraction"
        }
    
    def _read_video_file(self, video_path: str) -> Optional[str]:
        """读取视频文件并编码为base64"""
        try:
            path = Path(video_path)
            if not path.exists():
                return None
            
            with open(path, 'rb') as f:
                video_bytes = f.read()
                return base64.b64encode(video_bytes).decode('utf-8')
        except Exception as e:
            print(f"读取视频失败: {e}")
            return None
    
    def _get_prompt_for_task(self, task: str) -> str:
        """根据任务类型获取prompt"""
        task_prompts = self.prompts.get("tasks", {})
        
        if task in task_prompts:
            return task_prompts[task].get("prompt", "")
        
        # 降级到默认prompt
        default_prompt = self.prompts.get("default_prompt", "")
        if default_prompt:
            return default_prompt.format(task=task)
        
        # 最终降级
        return f"请分析这个视频并完成以下任务: {task}"
    
    async def describe_video(self, video_path: str) -> Dict[str, Any]:
        """描述视频内容"""
        return await self.analyze_video(video_path, task="describe")
    
    async def detect_actions(self, video_path: str) -> Dict[str, Any]:
        """检测视频中的动作"""
        return await self.analyze_video(video_path, task="action")
    
    async def analyze_scene(self, video_path: str) -> Dict[str, Any]:
        """分析视频场景"""
        return await self.analyze_video(video_path, task="scene")
    
    async def detect_emotions(self, video_path: str) -> Dict[str, Any]:
        """检测视频中的情感"""
        return await self.analyze_video(video_path, task="emotion")


# 使用示例
if __name__ == "__main__":
    import asyncio
    
    async def test():
        analyzer = VideoAnalyzer()
        
        # 测试视频路径
        video_path = "test_video.mp4"
        
        # 描述视频
        result = await analyzer.describe_video(video_path)
        print(f"描述结果: {result}")
        
        # 检测动作
        result = await analyzer.detect_actions(video_path)
        print(f"动作检测: {result}")
    
    asyncio.run(test())

