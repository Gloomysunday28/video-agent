"""
意图识别器
识别用户输入的意图类型
"""

import re
import httpx
from enum import Enum
from typing import Dict, Any, Optional, List
from pathlib import Path
import yaml


class IntentType(Enum):
    """意图类型"""
    # 视频相关
    GENERATE_VIDEO = "generate_video"  # 生成视频
    EDIT_VIDEO = "edit_video"          # 编辑视频
    ANALYZE_VIDEO = "analyze_video"    # 分析视频
    
    # 对话相关
    CHAT = "chat"                      # 普通聊天
    QUESTION = "question"              # 提问
    
    # 系统相关
    HELP = "help"                      # 帮助
    SETTINGS = "settings"              # 设置
    
    # 未知
    UNKNOWN = "unknown"


class IntentRecognizer:
    """
    意图识别器
    支持基于规则和基于LLM的识别
    """
    
    def __init__(
        self,
        use_llm: bool = True,
        config_path: Optional[str] = None,
        prompt_path: Optional[str] = None
    ):
        """
        初始化意图识别器
        
        Args:
            use_llm: 是否使用LLM识别
            config_path: LLM配置文件路径
            prompt_path: Prompt配置文件路径
        """
        self.use_llm = use_llm
        
        # 加载LLM配置
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "index.yml"
        self.config = self._load_config(config_path)
        
        # 加载Prompt配置
        if prompt_path is None:
            prompt_path = Path(__file__).parent.parent.parent / "prompts" / "intent-recognition" / "index.yml"
        self.prompts = self._load_config(prompt_path)
        
        # 从配置文件加载关键词规则
        self.intent_keywords = self._load_keywords_from_config()
    
    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """加载配置文件"""
        if not config_path.exists():
            return {}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _load_keywords_from_config(self) -> Dict[IntentType, List[str]]:
        """从配置文件加载关键词"""
        keywords_map = {}
        
        intent_types_config = self.prompts.get("intent_types", {})
        
        for intent_name, intent_data in intent_types_config.items():
            try:
                intent_type = IntentType(intent_name)
                keywords = intent_data.get("keywords", [])
                if keywords:
                    keywords_map[intent_type] = keywords
            except ValueError:
                # 忽略未知的意图类型
                pass
        
        return keywords_map
    
    async def recognize(self, text: str, context: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        识别意图（支持上下文）
        
        Args:
            text: 用户输入文本
            context: 对话上下文历史 [{"role": "user"/"assistant", "content": "..."}, ...]
        
        Returns:
            {
                "intent": IntentType,
                "confidence": float,
                "entities": dict,
                "method": "rule" | "llm"
            }
        """
        print(f"[意图识别] 输入文本: {text}")
        if context:
            print(f"[意图识别] 上下文消息数: {len(context)}")
        
        # 先尝试规则匹配
        print(f"[意图识别] 尝试规则匹配...")
        rule_result = self._recognize_by_rules(text)
        print(f"[意图识别] 规则匹配结果: {rule_result['intent'].value}, 置信度: {rule_result['confidence']:.2f}")
        
        # 如果规则匹配置信度高，直接返回
        if rule_result["confidence"] >= 0.8:
            print(f"[意图识别] ✓ 规则匹配置信度高 (≥0.8)，使用规则结果")
            return rule_result
        
        # 否则使用LLM（带上下文）
        if self.use_llm:
            print(f"[意图识别] 规则匹配置信度不够，尝试 LLM 识别（带上下文）...")
            llm_result = await self._recognize_by_llm(text, context=context)
            print(f"[意图识别] LLM 识别结果: {llm_result['intent'].value}, 置信度: {llm_result['confidence']:.2f}")
            # 如果LLM识别成功，返回LLM结果
            if llm_result["confidence"] >= 0.5:
                print(f"[意图识别] ✓ LLM 识别置信度可用 (≥0.5)，使用 LLM 结果")
                return llm_result
        
        # 都不行就返回规则结果
        print(f"[意图识别] ✓ 降级使用规则结果")
        return rule_result
    
    def _recognize_by_rules(self, text: str) -> Dict[str, Any]:
        """基于规则的识别"""
        text_lower = text.lower()
        
        # 检查每个意图的关键词
        scores = {}
        for intent_type, keywords in self.intent_keywords.items():
            score = 0
            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    score += 1
                    matched_keywords.append(keyword)
            
            if score > 0:
                scores[intent_type] = {
                    "score": score,
                    "keywords": matched_keywords
                }
        
        # 如果有匹配，返回最高分的
        if scores:
            best_intent = max(scores.items(), key=lambda x: x[1]["score"])
            intent_type = best_intent[0]
            confidence = min(best_intent[1]["score"] * 0.3, 0.9)
            
            return {
                "intent": intent_type,
                "confidence": confidence,
                "entities": self._extract_entities(text, intent_type),
                "method": "rule",
                "matched_keywords": best_intent[1]["keywords"]
            }
        
        # 没有匹配到，默认为聊天
        return {
            "intent": IntentType.CHAT,
            "confidence": 0.3,
            "entities": {},
            "method": "rule"
        }
    
    async def _recognize_by_llm(self, text: str, context: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """基于LLM的识别（支持上下文）"""
        llm_config = self.config.get("textLLM", {})
        api_key = llm_config.get("apiKey")
        base_url = llm_config.get("baseUrl")
        model = llm_config.get("model", "gpt-4o")
        
        if not api_key or not base_url:
            return {
                "intent": IntentType.UNKNOWN,
                "confidence": 0.0,
                "entities": {},
                "method": "llm",
                "error": "LLM未配置"
            }
        
        # 构建消息列表
        messages = []
        
        # 系统提示
        system_prompt = self.prompts.get("system_prompt", "你是一个专业的意图识别助手。")
        messages.append({"role": "system", "content": system_prompt})
        
        # 添加对话上下文（如果有）
        if context and len(context) > 0:
            # 只取最近几条消息（避免超过token限制）
            recent_context = context[-4:] if len(context) > 4 else context
            for msg in recent_context:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # 添加意图识别指令
        prompt_template = self.prompts.get("intent_recognition_prompt", "")
        if not prompt_template:
            fallback_template = self.prompts.get("fallback_prompt", "")
            if fallback_template:
                intent_list = ', '.join([intent.value for intent in IntentType])
                prompt = fallback_template.format(
                    intent_list=intent_list,
                    user_input=text
                )
            else:
                return {
                    "intent": IntentType.UNKNOWN,
                    "confidence": 0.0,
                    "entities": {},
                    "method": "llm",
                    "error": "Prompt配置未找到"
                }
        else:
            prompt = prompt_template.format(user_input=text)
        
        messages.append({"role": "user", "content": prompt})

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 50
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    intent_str = result["choices"][0]["message"]["content"].strip().lower()
                    
                    # 尝试匹配意图类型
                    for intent_type in IntentType:
                        if intent_type.value in intent_str:
                            return {
                                "intent": intent_type,
                                "confidence": 0.85,
                                "entities": self._extract_entities(text, intent_type),
                                "method": "llm"
                            }
                    
                    # 没匹配到，返回未知
                    return {
                        "intent": IntentType.UNKNOWN,
                        "confidence": 0.5,
                        "entities": {},
                        "method": "llm",
                        "raw_response": intent_str
                    }
                else:
                    return {
                        "intent": IntentType.UNKNOWN,
                        "confidence": 0.0,
                        "entities": {},
                        "method": "llm",
                        "error": f"LLM API错误: {response.status_code}"
                    }
                    
        except Exception as e:
            return {
                "intent": IntentType.UNKNOWN,
                "confidence": 0.0,
                "entities": {},
                "method": "llm",
                "error": str(e)
            }
    
    def _extract_entities(self, text: str, intent_type: IntentType) -> Dict[str, Any]:
        """提取实体信息"""
        entities = {}
        
        if intent_type == IntentType.GENERATE_VIDEO:
            # 提取视频相关参数
            # 时长
            duration_match = re.search(r'(\d+)\s*秒', text)
            if duration_match:
                entities["duration"] = int(duration_match.group(1))
            
            # 分辨率
            if "720p" in text.lower() or "720" in text:
                entities["resolution"] = "720p"
            elif "1080p" in text.lower() or "1080" in text:
                entities["resolution"] = "1080p"
            
            # 宽高比
            if "16:9" in text or "16比9" in text:
                entities["aspect_ratio"] = "16:9"
            elif "9:16" in text or "9比16" in text:
                entities["aspect_ratio"] = "9:16"
            
            # 提取描述（去除参数后的文本）
            description = text
            for pattern in [r'\d+秒', r'\d+p', r'\d+:\d+']:
                description = re.sub(pattern, '', description)
            entities["description"] = description.strip()
        
        return entities
    
    def recognize_sync(self, text: str) -> Dict[str, Any]:
        """同步版本的识别（只使用规则）"""
        return self._recognize_by_rules(text)


# 使用示例
if __name__ == "__main__":
    import asyncio
    
    async def test():
        recognizer = IntentRecognizer(use_llm=True)
        
        test_cases = [
            "帮我生成一个5秒的视频，内容是一只猫在草地上玩耍",
            "我想编辑这个视频",
            "分析一下这个视频内容",
            "今天天气怎么样？",
            "怎么使用这个工具？",
        ]
        
        for text in test_cases:
            print(f"\n输入: {text}")
            result = await recognizer.recognize(text)
            print(f"意图: {result['intent'].value}")
            print(f"置信度: {result['confidence']:.2f}")
            print(f"方法: {result['method']}")
            if result.get('entities'):
                print(f"实体: {result['entities']}")
    
    asyncio.run(test())

