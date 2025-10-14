"""
剪映视频生成器
通过剪映云API生成视频
"""

import httpx
import json
import uuid
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class JianyingConfig:
    """剪映API配置"""
    web_id: str
    ms_token: str
    generate_sign: str
    status_sign: str
    generate_a_bogus: str
    status_a_bogus: str
    cookies: Dict[str, str]
    base_url: str = "https://jimeng.jianying.com/mweb"


class JianyingVideoGenerator:
    """
    剪映视频生成器
    支持通过剪映云API生成视频
    """
    
    def __init__(self, config: JianyingConfig):
        """
        初始化生成器
        
        Args:
            config: 剪映API配置
        """
        self.config = config
        self.aid = "513695"
        self.device_platform = "web"
        self.region = "cn"
        self.da_version = "3.3.3"
        self.web_version = "7.5.0"
        self.aigc_features = "app_lip_sync"
    
    def _build_common_params(self, sign: str, a_bogus: str) -> Dict[str, str]:
        """构建通用URL参数"""
        return {
            "aid": self.aid,
            "device_platform": self.device_platform,
            "region": self.region,
            "webId": self.config.web_id,
            "da_version": self.da_version,
            "web_version": self.web_version,
            "aigc_features": self.aigc_features,
            "msToken": self.config.ms_token,
            "a_bogus": a_bogus,
        }
    
    def _build_common_headers(self, sign: str, referer: str) -> Dict[str, str]:
        """构建通用请求头"""
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "app-sdk-version": "48.0.0",
            "appid": self.aid,
            "appvr": "8.4.0",
            "content-type": "application/json",
            "device-time": str(int(time.time())),
            "lan": "zh-Hans",
            "loc": self.region,
            "pf": "7",
            "priority": "u=1, i",
            "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "sign": sign,
            "sign-ver": "1",
            "tdid": "",
            "referer": referer,
        }
    
    def _build_draft_content(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        duration_ms: int = 5000,
        resolution: str = "720p",
        seed: Optional[int] = None
    ) -> str:
        """构建draft_content JSON"""
        if seed is None:
            seed = int(time.time() * 1000) % 2147483647
        
        draft = {
            "type": "draft",
            "id": str(uuid.uuid4()),
            "min_version": "3.0.5",
            "min_features": [],
            "is_from_tsn": True,
            "version": self.da_version,
            "main_component_id": str(uuid.uuid4()),
            "component_list": [
                {
                    "type": "video_base_component",
                    "id": str(uuid.uuid4()),
                    "min_version": "1.0.0",
                    "aigc_mode": "workbench",
                    "metadata": {
                        "type": "",
                        "id": str(uuid.uuid4()),
                        "created_platform": 3,
                        "created_platform_version": "",
                        "created_time_in_ms": str(int(time.time() * 1000)),
                        "created_did": ""
                    },
                    "generate_type": "gen_video",
                    "abilities": {
                        "type": "",
                        "id": str(uuid.uuid4()),
                        "gen_video": {
                            "type": "",
                            "id": str(uuid.uuid4()),
                            "text_to_video_params": {
                                "type": "",
                                "id": str(uuid.uuid4()),
                                "video_gen_inputs": [
                                    {
                                        "type": "",
                                        "id": str(uuid.uuid4()),
                                        "min_version": "3.0.5",
                                        "prompt": prompt,
                                        "video_mode": 2,
                                        "fps": 24,
                                        "duration_ms": duration_ms,
                                        "resolution": resolution,
                                        "idip_meta_list": []
                                    }
                                ],
                                "video_aspect_ratio": aspect_ratio,
                                "seed": seed,
                                "model_req_key": "dreamina_ic_generate_video_model_vgfm_3.0",
                                "priority": 0
                            },
                            "video_task_extra": json.dumps({
                                "promptSource": "custom",
                                "isDefaultSeed": 1,
                                "originSubmitId": str(uuid.uuid4()),
                                "isRegenerate": False,
                                "enterFrom": "click",
                                "functionMode": "first_last_frames"
                            })
                        }
                    },
                    "process_type": 1
                }
            ]
        }
        
        return json.dumps(draft)
    
    async def generate_video(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        duration: int = 5,
        resolution: str = "720p",
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        生成视频
        
        Args:
            prompt: 视频描述文本
            aspect_ratio: 宽高比 (16:9, 9:16等)
            duration: 时长（秒）
            resolution: 分辨率 (720p, 1080p)
            seed: 随机种子（可选）
        
        Returns:
            {
                "success": bool,
                "submit_id": str,      # 提交ID，用于查询状态
                "message": str,
                "raw_response": dict
            }
        """
        submit_id = str(uuid.uuid4())
        duration_ms = duration * 1000
        
        # 构建请求体
        metrics_extra = {
            "promptSource": "custom",
            "isDefaultSeed": 1,
            "originSubmitId": submit_id,
            "isRegenerate": False,
            "enterFrom": "click",
            "functionMode": "first_last_frames"
        }
        
        draft_content = self._build_draft_content(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            duration_ms=duration_ms,
            resolution=resolution,
            seed=seed
        )
        
        body = {
            "extend": {
                "root_model": "dreamina_ic_generate_video_model_vgfm_3.0",
                "m_video_commerce_info": {
                    "benefit_type": "basic_video_operation_vgfm_v_three",
                    "resource_id": "generate_video",
                    "resource_id_type": "str",
                    "resource_sub_type": "aigc"
                },
                "m_video_commerce_info_list": [
                    {
                        "benefit_type": "basic_video_operation_vgfm_v_three",
                        "resource_id": "generate_video",
                        "resource_id_type": "str",
                        "resource_sub_type": "aigc"
                    }
                ]
            },
            "submit_id": submit_id,
            "metrics_extra": json.dumps(metrics_extra),
            "draft_content": draft_content,
            "http_common_info": {
                "aid": int(self.aid)
            }
        }
        
        # 构建URL
        params = self._build_common_params(
            sign=self.config.generate_sign,
            a_bogus=self.config.generate_a_bogus
        )
        params["web_component_open_flag"] = "1"
        
        url = f"{self.config.base_url}/v1/aigc_draft/generate"
        
        # 构建headers
        headers = self._build_common_headers(
            sign=self.config.generate_sign,
            referer="https://jimeng.jianying.com/ai-tool/home?type=video"
        )
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    params=params,
                    headers=headers,
                    cookies=self.config.cookies,
                    json=body
                )
                
                print(f"生成视频响应状态: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    
                    return {
                        "success": True,
                        "submit_id": submit_id,
                        "message": "视频生成任务已提交",
                        "raw_response": result
                    }
                else:
                    return {
                        "success": False,
                        "submit_id": submit_id,
                        "message": f"API错误: {response.status_code}",
                        "error": response.text
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "submit_id": submit_id,
                "message": f"请求失败: {str(e)}",
                "error": str(e)
            }
    
    async def get_video_status(self, submit_id: str) -> Dict[str, Any]:
        """
        查询视频生成状态
        
        Args:
            submit_id: 提交ID
        
        Returns:
            {
                "success": bool,
                "status": str,         # pending, processing, completed, failed
                "progress": float,     # 0-100
                "video_url": str,      # 视频URL（如果完成）
                "message": str,
                "raw_response": dict
            }
        """
        # 构建URL
        params = self._build_common_params(
            sign=self.config.status_sign,
            a_bogus=self.config.status_a_bogus
        )
        
        url = f"{self.config.base_url}/v1/get_history_by_ids"
        
        # 构建headers
        headers = self._build_common_headers(
            sign=self.config.status_sign,
            referer="https://jimeng.jianying.com/ai-tool/generate"
        )
        
        # 请求体
        body = {
            "submit_ids": [submit_id]
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    params=params,
                    headers=headers,
                    cookies=self.config.cookies,
                    json=body
                )
                
                print(f"查询状态响应: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # 解析状态
                    # TODO: 根据实际API响应格式解析状态
                    
                    return {
                        "success": True,
                        "status": "unknown",
                        "message": "状态查询成功",
                        "raw_response": result
                    }
                else:
                    return {
                        "success": False,
                        "message": f"API错误: {response.status_code}",
                        "error": response.text
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "message": f"请求失败: {str(e)}",
                "error": str(e)
            }


# 使用示例
if __name__ == "__main__":
    import asyncio
    
    async def test():
        # 配置（使用你提供的实际参数）
        config = JianyingConfig(
            web_id="7537987985893295667",
            ms_token="r2x9AF3dAqUa8qQ8lEtVPKSuzVx2dHF96xFvqOaTF74MNAP9nOTRMy7KPx5Yiq062XtdbHN2yJWb6blITzIdU-1XF6eftMAaKyhjgFttb86qD2JjpPALd4je7SoV4Bo=",
            generate_sign="a9d4740de3fd4dfff79d40f0553259d6",
            status_sign="4b8238b1156833f21a61bbfb1e396caa",
            generate_a_bogus="Y6BEgOhGMsm1MPUdJ7kz9eT-yGy0YW5FgZENQecmHtwy",
            status_a_bogus="DvUQXOhGMsm1auUdJwkz9H79yH80YW4ogZENQetohzwC",
            cookies={
                # 这里需要填入实际的cookies
                # 从浏览器开发者工具中复制
            }
        )
        
        generator = JianyingVideoGenerator(config)
        
        # 生成视频
        print("开始生成视频...")
        result = await generator.generate_video(
            prompt="一只可爱的小猫在草地上玩耍",
            aspect_ratio="16:9",
            duration=5,
            resolution="720p"
        )
        
        print(f"生成结果: {result}")
        
        if result["success"]:
            submit_id = result["submit_id"]
            
            # 查询状态
            print(f"\n查询状态 (submit_id: {submit_id})...")
            status = await generator.get_video_status(submit_id)
            print(f"状态结果: {status}")
    
    asyncio.run(test())

