"""
Agent调度器
负责意图识别、工具调度和上下文管理
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import yaml

from agent.tools.intent_recognition import IntentRecognizer, IntentType
from agent.tools.generate import JianyingVideoGenerator, JianyingConfig
from agent.tools.vision import VideoAnalyzer
from agent.context.manager import ContextManager


class AgentScheduler:
    """
    Agent核心调度器
    
    工作流程：
    1. 接收用户输入
    2. 识别意图
    3. 根据意图调用对应工具
    4. 管理上下文（存储、检索、压缩）
    5. 返回结果
    """
    
    def __init__(
        self,
        session_id: str = "default",
        use_llm_intent: bool = True,
        context_compression_threshold: int = 10000
    ):
        """
        初始化调度器
        
        Args:
            session_id: 会话ID
            use_llm_intent: 是否使用LLM进行意图识别
            context_compression_threshold: 上下文压缩阈值（默认10000字符）
        """
        self.session_id = session_id
        
        # 加载配置
        config = self._load_config()
        
        # 初始化意图识别器
        self.intent_recognizer = IntentRecognizer(use_llm=use_llm_intent)
        
        # 从配置获取 LLM API 信息
        text_llm = config.get("textLLM", {})
        llm_api_url = text_llm.get("baseUrl")
        llm_api_key = text_llm.get("apiKey")
        
        # 初始化上下文管理器（带意图识别增强压缩和向量存储）
        self.context_manager = ContextManager(
            max_context_length=100000,
            auto_compress_threshold=context_compression_threshold,
            session_id=session_id,
            llm_api_url=llm_api_url,
            llm_api_key=llm_api_key
        )
        
        # 注入意图识别器到上下文管理器（用于压缩时的意图识别）
        self.context_manager.set_intent_recognizer(self.intent_recognizer)
        
        # 工具注册表
        self.tools = {}
        self._register_tools()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        config_path = Path(__file__).parent.parent / "config" / "index.yml"
        if not config_path.exists():
            print(f"[调度器] 配置文件不存在: {config_path}")
            return {}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _register_tools(self):
        """注册可用工具"""
        # 视频生成工具
        self.tools["video_generator"] = None  # 延迟加载
        
        # 视频分析工具
        self.tools["video_analyzer"] = VideoAnalyzer()
    
    async def process(self, user_input: str, **kwargs) -> Dict[str, Any]:
        """
        处理用户输入（Reaction 架构）
        
        工作流程：
        1. 输入信号：接收用户输入
        2. 检查待处理任务：是否有未完成的任务在等待参数
        3. 识别意图：理解用户意图（或提取待处理任务的参数）
        4. 选择反应：根据意图/任务选择工具
        5. 执行动作：调用工具
        6. 感知结果：检查执行结果，如果缺少参数则设置待处理任务
        7. 新反应：返回结果或提示用户提供更多信息
        
        Args:
            user_input: 用户输入文本
            **kwargs: 额外参数
        
        Returns:
            {
                "success": bool,
                "intent": str,
                "result": Any,
                "context_info": dict
            }
        """
        # 1. 添加用户输入到上下文
        self.context_manager.add_message(
            role="user",
            content=user_input,
            metadata={"timestamp": self._get_timestamp()}
        )
        
        # 2. [Reaction 架构] 检查是否有待处理任务
        pending_task = self.context_manager.get_pending_task()
        intent_result = None  # 初始化
        
        if pending_task:
            print(f"[调度器 - Reaction] 检测到待处理任务: {pending_task['type']}")
            print(f"[调度器 - Reaction] 尝试从用户输入中提取参数: {pending_task['required_params']}")
            
            # 尝试从用户输入中提取参数
            extracted_params = self._extract_params_from_input(user_input, pending_task['required_params'])
            
            if extracted_params:
                print(f"[调度器 - Reaction] ✓ 成功提取参数: {extracted_params}")
                # 参数齐全，继续执行任务
                self.context_manager.clear_pending_task()
                
                # 直接调用对应的处理方法
                if pending_task['type'] == 'analyze_video':
                    result = await self._handle_analyze_video(user_input, {}, **extracted_params)
                    intent_type = IntentType.ANALYZE_VIDEO
                    confidence = 1.0
                    entities = extracted_params
                    # 构造 intent_result 用于后续日志
                    intent_result = {
                        "intent": intent_type,
                        "confidence": confidence,
                        "entities": entities,
                        "method": "reaction"
                    }
                else:
                    result = {"success": False, "message": f"未知的待处理任务类型: {pending_task['type']}"}
                    intent_type = IntentType.UNKNOWN
                    confidence = 0.0
                    entities = {}
                    intent_result = {
                        "intent": intent_type,
                        "confidence": confidence,
                        "entities": entities,
                        "method": "reaction"
                    }
            else:
                print(f"[调度器 - Reaction] ✗ 无法提取参数，继续等待")
                return {
                    "success": False,
                    "intent": pending_task['type'],
                    "result": {
                        "message": f"未能识别到所需参数，请提供: {', '.join(pending_task['required_params'])}"
                    }
                }
        else:
            # 3. 正常识别意图（带上下文）
            print(f"[调度器] 开始识别意图，用户输入: {user_input}")
            
            # 获取最近的对话历史作为上下文
            context_history = self._get_context_for_intent_recognition()
            
            intent_result = await self.intent_recognizer.recognize(user_input, context=context_history)
            intent_type = intent_result["intent"]
            confidence = intent_result["confidence"]
            entities = intent_result.get("entities", {})
        
        print(f"[调度器] ✓ 意图识别完成")
        print(f"[调度器]   - 意图类型: {intent_type.value}")
        print(f"[调度器]   - 置信度: {confidence:.2f}")
        print(f"[调度器]   - 提取实体: {entities}")
        if intent_result:
            print(f"[调度器]   - 识别方法: {intent_result.get('method', 'unknown')}")
        
        # 3. 根据意图调度工具
        try:
            if intent_type == IntentType.GENERATE_VIDEO:
                print(f"[调度器] → 调用工具: 视频生成 (generate_video)")
                result = await self._handle_generate_video(user_input, entities, **kwargs)
                print(f"[调度器] ← 工具返回: {result}")
            
            elif intent_type == IntentType.ANALYZE_VIDEO:
                print(f"[调度器] → 调用工具: 视频分析 (analyze_video)")
                result = await self._handle_analyze_video(user_input, entities, **kwargs)
                print(f"[调度器] ← 工具返回: {result}")
            
            elif intent_type == IntentType.HELP:
                print(f"[调度器] → 调用工具: 帮助 (help)")
                result = self._handle_help()
                print(f"[调度器] ← 工具返回: {result}")
            
            elif intent_type == IntentType.CHAT or intent_type == IntentType.QUESTION:
                print(f"[调度器] → 调用工具: 对话 (chat)")
                result = await self._handle_chat(user_input, **kwargs)
                print(f"[调度器] ← 工具返回: {result}")
            
            else:
                print(f"[调度器] ✗ 未知意图类型: {intent_type.value}")
                result = {
                    "success": False,
                    "message": f"暂不支持的意图类型: {intent_type.value}"
                }
            
            # 4. 添加结果到上下文
            # 提取实际的内容（而不是整个字典）
            if isinstance(result, dict):
                # 优先提取 result 字段，其次 message 字段
                assistant_content = result.get("result") or result.get("message") or str(result)
            else:
                assistant_content = str(result)
            
            self.context_manager.add_message(
                role="assistant",
                content=assistant_content,
                metadata={
                    "timestamp": self._get_timestamp(),
                    "intent": intent_type.value,
                    "confidence": confidence,
                    "success": result.get("success") if isinstance(result, dict) else None
                }
            )
            
            # 5. 返回结果
            return {
                "success": result.get("success", True),
                "intent": intent_type.value,
                "confidence": confidence,
                "entities": entities,
                "result": result,
                "context_info": {
                    "length": len(self.context_manager.get_full_context()),
                    "messages": len(self.context_manager.memory_store.get_history())
                }
            }
            
        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            
            # 记录错误到上下文
            self.context_manager.add_message(
                role="system",
                content=f"错误: {error_msg}",
                metadata={"timestamp": self._get_timestamp()}
            )
            
            return {
                "success": False,
                "intent": intent_type.value,
                "error": error_msg,
                "context_info": {
                    "length": len(self.context_manager.get_full_context()),
                    "messages": len(self.context_manager.memory_store.get_history())
                }
            }
    
    async def _handle_generate_video(
        self,
        user_input: str,
        entities: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """处理视频生成请求"""
        # 从实体或kwargs中提取参数
        prompt = entities.get("description", user_input)
        aspect_ratio = entities.get("aspect_ratio", kwargs.get("aspect_ratio", "16:9"))
        duration = entities.get("duration", kwargs.get("duration", 5))
        resolution = entities.get("resolution", kwargs.get("resolution", "720p"))
        
        print(f"[调度器] 生成视频 - prompt: {prompt}, 宽高比: {aspect_ratio}, 时长: {duration}秒")
        
        # 延迟加载视频生成器（需要配置）
        if self.tools["video_generator"] is None:
            self.tools["video_generator"] = self._create_video_generator()
        
        generator = self.tools["video_generator"]
        
        # 调用生成工具
        result = await generator.generate_video(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            duration=duration,
            resolution=resolution
        )
        
        return result
    
    async def _handle_analyze_video(
        self,
        user_input: str,
        entities: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """处理视频分析请求"""
        import re
        
        # 1. 优先从 kwargs 获取
        video_path = kwargs.get("video_path")
        
        # 2. 从 entities 获取
        if not video_path:
            video_path = entities.get("video_url") or entities.get("url")
        
        # 3. 从用户输入中提取 URL
        if not video_path:
            # 匹配 http:// 或 https:// 开头的 URL
            url_pattern = r'https?://[^\s]+'
            urls = re.findall(url_pattern, user_input)
            if urls:
                video_path = urls[0]
        
        if not video_path:
            # [Reaction 架构] 设置待处理任务，等待用户提供视频URL
            print(f"[调度器 - Reaction] 缺少视频路径，设置待处理任务")
            self.context_manager.set_pending_task(
                task_type="analyze_video",
                required_params=["video_path"],
                context={"user_input": user_input}
            )
            return {
                "success": False,
                "message": "需要提供视频路径，请在消息中包含视频 URL"
            }
        
        print(f"[调度器] 分析视频 - 路径: {video_path}")
        
        analyzer = self.tools["video_analyzer"]
        
        # 调用分析工具
        result = await analyzer.describe_video(video_path)
        
        return result
    
    def _handle_help(self) -> Dict[str, Any]:
        """处理帮助请求"""
        help_text = """
🤖 视频Agent助手

可用功能：
1. 📹 生成视频 - 通过描述文本生成视频
   示例: "生成一个5秒的视频，内容是一只猫在草地上玩耍"
   
2. 🔍 分析视频 - 分析视频内容
   示例: "分析这个视频的内容"
   
3. 💬 对话交流 - 普通对话
   
参数说明：
- 宽高比: 16:9, 9:16 等
- 时长: 1-10秒
- 分辨率: 720p, 1080p

使用 /help 查看此帮助信息
        """
        
        return {
            "success": True,
            "message": help_text.strip()
        }
    
    async def _handle_chat(
        self,
        user_input: str,
        **kwargs
    ) -> Dict[str, Any]:
        """处理普通对话"""
        # TODO: 集成对话LLM
        return {
            "success": True,
            "message": "普通对话功能待实现，当前仅支持视频生成和分析。",
            "user_input": user_input
        }
    
    def _create_video_generator(self) -> JianyingVideoGenerator:
        """创建视频生成器（从配置加载）"""
        from pathlib import Path
        import yaml
        
        config_path = Path(__file__).parent.parent / "config" / "index.yml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        jianying_cfg = config.get("jianyingAPI", {})
        
        jianying_config = JianyingConfig(
            web_id=jianying_cfg.get("webId", ""),
            ms_token=jianying_cfg.get("msToken", ""),
            generate_sign=jianying_cfg.get("generateSign", ""),
            status_sign=jianying_cfg.get("statusSign", ""),
            generate_a_bogus=jianying_cfg.get("generateABogus", ""),
            status_a_bogus=jianying_cfg.get("statusABogus", ""),
            cookies=jianying_cfg.get("cookies", {})
        )
        
        return JianyingVideoGenerator(jianying_config)
    
    def _get_timestamp(self) -> int:
        """获取当前时间戳"""
        import time
        return int(time.time())
    
    def _get_context_for_intent_recognition(self) -> List[Dict[str, str]]:
        """
        获取用于意图识别的上下文历史
        
        Returns:
            对话历史列表 [{"role": "user"/"assistant", "content": "..."}, ...]
        """
        history = self.context_manager.memory_store.get_history()
        
        # 只取最近几条（避免太长）
        recent_history = history[-6:] if len(history) > 6 else history
        
        # 转换为 LLM 需要的格式
        context = []
        for msg in recent_history:
            # msg 可能是字典或对象
            if isinstance(msg, dict):
                role = msg.get('role', 'user')
                content = msg.get('content', '')
            else:
                role = getattr(msg, 'role', 'user')
                content = getattr(msg, 'content', '')
            
            context.append({
                "role": role,
                "content": content[:500]  # 限制长度，避免超token
            })
        
        return context
    
    def _extract_params_from_input(self, user_input: str, required_params: List[str]) -> Dict[str, Any]:
        """
        从用户输入中提取参数（Reaction 架构）
        
        Args:
            user_input: 用户输入
            required_params: 需要的参数列表
        
        Returns:
            提取到的参数字典
        """
        import re
        extracted = {}
        
        for param in required_params:
            if param == "video_path" or param == "video_url":
                # 提取 URL
                url_pattern = r'https?://[^\s]+'
                urls = re.findall(url_pattern, user_input)
                if urls:
                    extracted["video_path"] = urls[0]
                    print(f"[参数提取] 找到视频URL: {urls[0][:50]}...")
            
            elif param == "prompt" or param == "description":
                # 提取描述文本（去除URL后的文本）
                text = re.sub(r'https?://[^\s]+', '', user_input).strip()
                if text:
                    extracted[param] = text
                    print(f"[参数提取] 找到描述: {text[:50]}...")
        
        return extracted
    
    def get_context_summary(self) -> Dict[str, Any]:
        """获取上下文摘要信息"""
        return {
            "session_id": self.session_id,
            "context_length": len(self.context_manager.get_full_context()),
            "message_count": len(self.context_manager.memory_store.get_history()),
            "compression_threshold": self.context_manager.compression_threshold
        }
    
    def clear_context(self):
        """清空上下文"""
        self.context_manager.memory_store.clear()
        print(f"[调度器] 会话 {self.session_id} 的上下文已清空")


# 使用示例
if __name__ == "__main__":
    import asyncio
    
    async def test():
        scheduler = AgentScheduler(session_id="test_session")
        
        # 测试1: 视频生成
        print("\n=== 测试1: 视频生成 ===")
        result = await scheduler.process(
            "帮我生成一个5秒的视频，内容是一只猫在草地上玩耍"
        )
        print(f"结果: {result}")
        
        # 测试2: 帮助
        print("\n=== 测试2: 帮助 ===")
        result = await scheduler.process("怎么使用？")
        print(f"结果: {result}")
        
        # 测试3: 上下文摘要
        print("\n=== 测试3: 上下文摘要 ===")
        summary = scheduler.get_context_summary()
        print(f"上下文摘要: {summary}")
    
    asyncio.run(test())

