"""
Agent调度器
负责意图识别、工具调度和上下文管理
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import yaml
import asyncio

from agent.tools.intent_recognition import IntentRecognizer, IntentType
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
            extracted_params = self._extract_params_from_input(user_input, pending_task['required_params'], **kwargs)
            
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
            
            # 优先检查文件类型来确定意图
            image_file = kwargs.get("image_file")
            video_file = kwargs.get("video_file")
            
            if image_file:
                # 如果上传了图片，直接识别为生成图片意图
                print(f"[调度器] 检测到图片文件，直接识别为生成图片意图")
                intent_type = IntentType.GENERATE_IMAGE
                confidence = 1.0
                entities = {"description": user_input}
                intent_result = {
                    "intent": intent_type,
                    "confidence": confidence,
                    "entities": entities,
                    "method": "file_based"
                }
            elif video_file:
                # 如果上传了视频，直接识别为分析视频意图
                print(f"[调度器] 检测到视频文件，直接识别为分析视频意图")
                intent_type = IntentType.ANALYZE_VIDEO
                confidence = 1.0
                entities = {"video_description": user_input}
                intent_result = {
                    "intent": intent_type,
                    "confidence": confidence,
                    "entities": entities,
                    "method": "file_based"
                }
            else:
                # 没有文件，使用正常的意图识别
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
            
            elif intent_type == IntentType.GENERATE_IMAGE:
                print(f"[调度器] → 调用工具: 图片生成 (generate_image)")
                result = await self._handle_generate_image(user_input, entities, **kwargs)
                print(f"[调度器] ← 图片生成工具返回: {result}")
                print(f"[调度器] 结果类型: {type(result)}, success: {result.get('success') if isinstance(result, dict) else 'N/A'}")
            
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
            
            elif intent_type == IntentType.UNKNOWN:
                print(f"[调度器] → 意图未识别，转为普通对话模式")
                result = await self._handle_chat(user_input, **kwargs)
                print(f"[调度器] ← 工具返回: {result}")
            
            else:
                print(f"[调度器] ✗ 未知意图类型: {intent_type.value}，转为普通对话模式")
                result = await self._handle_chat(user_input, **kwargs)
                print(f"[调度器] ← 工具返回: {result}")
            
            # 4. 添加结果到上下文
            # 提取实际的内容（而不是整个字典）
            if isinstance(result, dict):
                # 优先提取 result 字段，其次 message 字段
                assistant_content = result.get("result") or result.get("message") or str(result)
                
                # 检查消息类型
                message_type = "text"  # 默认类型
                if intent_type == IntentType.GENERATE_IMAGE:
                    # 图片生成结果
                    message_type = "image"
                    # 对于图片消息，content 直接是图片URL，不需要额外的文案
                    if result.get("image_url"):  # 优先使用image_url字段
                        assistant_content = result.get("image_url")
                    elif result.get("video_url"):  # 兼容性：豆包图片生成器返回的video_url字段
                        assistant_content = result.get("video_url")
                    elif result.get("video_path"):  # 兼容其他可能的字段名
                        assistant_content = result.get("video_path")
                elif result.get("video_path") or result.get("video_url"):
                    # 视频生成结果
                    message_type = "video"
                    # 对于视频消息，content 直接是视频URL，不需要额外的文案
                    if result.get("video_url"):
                        assistant_content = result.get("video_url")
                    elif result.get("video_path"):
                        assistant_content = result.get("video_path")
            else:
                assistant_content = str(result)
                message_type = "text"
            
            self.context_manager.add_message(
                role="assistant",
                content=assistant_content,
                metadata={
                    "timestamp": self._get_timestamp(),
                    "intent": intent_type.value,
                    "confidence": confidence,
                    "success": result.get("success") if isinstance(result, dict) else None,
                    "title": intent_result.get("title") if intent_result else None,  # 添加标题
                    "message_type": message_type  # 添加消息类型
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
        # 导入WebSocket状态推送功能
        # 不再需要实时状态推送
        has_sse = False
        # 兼容旧逻辑，防止未定义变量报错（当前不使用 WebSocket 推送）
        has_websocket = False
        
        # 从实体或kwargs中提取参数
        prompt = entities.get("description", user_input)
        aspect_ratio = entities.get("aspect_ratio", kwargs.get("aspect_ratio", "16:9"))
        duration = entities.get("duration", kwargs.get("duration", 5))
        resolution = entities.get("resolution", kwargs.get("resolution", "720p"))
        generator_type = kwargs.get("generator_type", "doubao")
        script_path = kwargs.get("script_path")
        
        print(f"[调度器] 生成视频 - prompt: {prompt}, 宽高比: {aspect_ratio}, 时长: {duration}秒, 生成器: {generator_type}")
        
        
        # 根据生成器类型选择生成器
        if generator_type == "doubao":
            print(f"[调度器] 使用豆包生成器")
            from agent.tools.generate import DoubaoVideoGenerator, DoubaoConfig
            from agent.api.common import load_doubao_config
            
            try:
                config = load_doubao_config()
                generator = DoubaoVideoGenerator(config)
                print(f"[调度器] ✓ 豆包生成器初始化成功")
            except Exception as e:
                print(f"[调度器] ✗ 豆包生成器初始化失败: {e}")
                return {
                    "success": False,
                    "message": f"豆包生成器初始化失败: {str(e)}"
                }
        elif generator_type == "jianying":
            print(f"[调度器] 使用剪映生成器")
            from agent.tools.generate import JianyingVideoGenerator, JianyingConfig
            from agent.api.common import load_jianying_config
            
            try:
                config = load_jianying_config()
                generator = JianyingVideoGenerator(config)
                print(f"[调度器] ✓ 剪映生成器初始化成功")
            except Exception as e:
                print(f"[调度器] ✗ 剪映生成器初始化失败: {e}")
                return {
                    "success": False,
                    "message": f"剪映生成器初始化失败: {str(e)}"
                }
        else:
            # 使用脚本生成器（默认）
            print(f"[调度器] 使用脚本生成器")
            if not script_path:
                # 使用默认脚本路径
                script_path = "/Users/weiguang/agent/agents/video-agent/src/agent/tools/generate/script_generator.py"
            
            from agent.tools.generate import ScriptVideoGenerator, ScriptConfig
            config = ScriptConfig(
                script_path=script_path,
                python_executable="python3.13",
                timeout=kwargs.get("timeout", 900)
            )
            generator = ScriptVideoGenerator(config)
            print(f"[调度器] ✓ 脚本生成器初始化成功")
            
            if False:  # 禁用实时状态推送
                await send_task_progress(
                    self.session_id,
                    "video_generation",
                    20.0,
                    "开始执行视频生成脚本..."
                )
        
        # 发送处理中状态
        if False:  # 禁用实时状态推送
            await send_task_status(
                self.session_id,
                "video_generation",
                "processing",
                "正在执行视频生成脚本..."
            )
        
        # 调用生成工具
        result = await generator.generate_video(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            duration=duration,
            resolution=resolution
        )
        
        # 如果剪映API调用时间较长，发送额外的进度更新
        if False:  # 禁用实时状态推送
            await send_task_progress(
                self.session_id,
                "video_generation",
                50.0,
                "剪映API调用完成，正在处理结果..."
            )
        
        # 根据生成器类型决定是否需要轮询状态
        if result.get("success") and result.get("submit_id"):
            if generator_type == "doubao":
                # 豆包生成器是同步的，不需要轮询
                print(f"[调度器] 豆包生成器是同步的，直接返回结果")
                pass
            else:
                # 其他生成器需要轮询状态
                if False:  # 禁用实时状态推送
                    await send_task_progress(
                        self.session_id,
                        "video_generation",
                        70.0,
                        "正在等待视频生成完成..."
                    )
                
                # 轮询视频状态
                submit_id = result.get("submit_id")
                max_attempts = 30  # 最多轮询30次
                attempt = 0
                
                while attempt < max_attempts:
                    await asyncio.sleep(5)  # 等待5秒
                    attempt += 1
                    
                    if False:  # 禁用实时状态推送
                        await send_task_progress(
                            self.session_id,
                            "video_generation",
                            70 + (attempt * 1),  # 从70%到100%
                            f"正在检查视频生成状态... ({attempt}/{max_attempts})"
                        )
                    
                    # 查询视频状态
                    status_result = await generator.get_video_status(submit_id)
                    
                    if status_result.get("success") and status_result.get("status") == "completed":
                        # 视频生成完成，获取URL
                        video_url = status_result.get("video_url")
                        if video_url:
                            result["video_url"] = video_url
                            result["message"] = "视频生成成功！"
                            
                            if False:  # 禁用实时状态推送
                                await send_task_completed(
                                    self.session_id,
                                    "video_generation",
                                    "视频生成成功！",
                                    result
                                )
                            break
                        else:
                            # 状态显示完成但没有URL，继续等待
                            continue
                    elif status_result.get("status") == "failed":
                        # 视频生成失败
                        result["success"] = False
                        result["message"] = "视频生成失败"
                        result["error"] = status_result.get("message", "未知错误")
                        
                        if False:  # 禁用实时状态推送
                            await send_task_error(
                                self.session_id,
                                "video_generation",
                                "视频生成失败",
                                result
                            )
                        break
                    else:
                        # 还在处理中，继续等待
                        continue
                
                # 如果超时还没有完成
                if attempt >= max_attempts:
                    result["message"] = "视频生成超时，请稍后手动查询"
                    if False:  # 禁用实时状态推送
                        await send_task_error(
                            self.session_id,
                            "video_generation",
                            "视频生成超时",
                            result
                        )
        
        # 发送完成状态（如果没有通过轮询处理）
        if has_websocket and not result.get("video_url"):
            if result.get("success"):
                await send_task_completed(
                    self.session_id,
                    "video_generation",
                    result.get("message", "视频生成任务已提交"),
                    result
                )
            else:
                await send_task_error(
                    self.session_id,
                    "video_generation",
                    result.get("message", "视频生成失败"),
                    result
                )
        
        return result
    
    async def _handle_generate_image(
        self,
        user_input: str,
        entities: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """处理图片生成请求（支持多模态）"""
        # 从实体或kwargs中提取参数
        prompt = entities.get("description", user_input)
        resolution = entities.get("resolution", kwargs.get("resolution", "720p"))
        generator_type = kwargs.get("generator_type", "doubao")
        
        # 获取参考图片（多模态支持）
        image_file = kwargs.get("image_file")
        image_filename = kwargs.get("image_filename")
        
        print(f"[调度器] 调试 - image_file: {image_file[:100] if image_file else None}")
        print(f"[调度器] 调试 - image_filename: {image_filename}")
        print(f"[调度器] 调试 - 所有kwargs: {list(kwargs.keys())}")
        
        if image_file:
            print(f"[调度器] 多模态图片生成 - prompt: {prompt}, 分辨率: {resolution}, 生成器: {generator_type}, 参考图片: {image_filename or '有图片数据'}")
        else:
            print(f"[调度器] 文本到图片生成 - prompt: {prompt}, 分辨率: {resolution}, 生成器: {generator_type}")
        
        # 根据生成器类型和是否有参考图片选择生成器
        if generator_type == "doubao":
            # 如果有参考图片，使用豆包生成器（支持多模态）
            if image_file:
                print(f"[调度器] 检测到参考图片，使用豆包生成器进行图生图")
                from agent.tools.generate.images.doubao_generator import DoubaoVideoGenerator, DoubaoConfig
                from agent.api.common import load_doubao_config
                
                try:
                    config = load_doubao_config()
                    generator = DoubaoVideoGenerator(config)
                    print(f"[调度器] ✓ 豆包图片生成器初始化成功")
                except Exception as e:
                    print(f"[调度器] ✗ 豆包图片生成器初始化失败: {e}")
                    return {
                        "success": False,
                        "message": f"豆包图片生成器初始化失败: {str(e)}"
                    }
            else:
                # 纯文生图，使用BetterYeah生成器
                print(f"[调度器] 纯文生图，使用BetterYeah图片生成器")
                from agent.tools.generate.images.betteryeah_generator import BetterYeahImageGenerator, BetterYeahConfig
                from agent.api.common import load_betteryeah_config
                
                try:
                    config = load_betteryeah_config()
                    generator = BetterYeahImageGenerator(config)
                    print(f"[调度器] ✓ BetterYeah图片生成器初始化成功")
                except Exception as e:
                    print(f"[调度器] ✗ BetterYeah图片生成器初始化失败: {e}")
                    return {
                        "success": False,
                        "message": f"BetterYeah图片生成器初始化失败: {str(e)}"
                    }
        elif generator_type == "betteryeah":
            print(f"[调度器] 使用BetterYeah图片生成器")
            from agent.tools.generate.images.betteryeah_generator import BetterYeahImageGenerator, BetterYeahConfig
            from agent.api.common import load_betteryeah_config
            
            try:
                config = load_betteryeah_config()
                generator = BetterYeahImageGenerator(config)
                print(f"[调度器] ✓ BetterYeah图片生成器初始化成功")
            except Exception as e:
                print(f"[调度器] ✗ BetterYeah图片生成器初始化失败: {e}")
                return {
                    "success": False,
                    "message": f"BetterYeah图片生成器初始化失败: {str(e)}"
                }
        else:
            return {
                "success": False,
                "message": f"不支持的图片生成器类型: {generator_type}，支持的类型: doubao, betteryeah"
            }
        
        # 准备参考图片参数
        reference_image = None
        if image_file:
            print(f"[调度器] 构建reference_image - image_file前100字符: {image_file[:100]}")
            # 判断是文件路径还是base64数据
            if image_file.startswith('file://'):
                # 是文件路径，直接使用
                reference_image = image_file
                print(f"[调度器] 使用文件路径: {reference_image}")
            elif image_file.startswith('data:image/'):
                # 已经是data URL格式，直接使用
                reference_image = image_file
                print(f"[调度器] 直接使用已有data:image格式: {reference_image[:100]}")
            else:
                # 假设是base64编码，添加data URL前缀
                reference_image = f"data:image/jpeg;base64,{image_file}"
                print(f"[调度器] 添加data:image前缀: {reference_image[:100]}")
        else:
            print(f"[调度器] 没有image_file，reference_image保持为None")
        
        # 如果没有参考图片，强制使用BetterYeah生成器
        if not reference_image and generator_type == "doubao":
            print(f"[调度器] 没有参考图片，强制使用BetterYeah生成器")
            from agent.tools.generate.images.betteryeah_generator import BetterYeahImageGenerator, BetterYeahConfig
            from agent.api.common import load_betteryeah_config
            
            try:
                config = load_betteryeah_config()
                generator = BetterYeahImageGenerator(config)
                print(f"[调度器] ✓ BetterYeah图片生成器初始化成功")
            except Exception as e:
                print(f"[调度器] ✗ BetterYeah图片生成器初始化失败: {e}")
                return {
                    "success": False,
                    "message": f"BetterYeah图片生成器初始化失败: {str(e)}"
                }
        
        # 调用生成工具
        result = await generator.generate_video(  # 豆包生成器的方法名是generate_video，但实际生成图片
            prompt=prompt,
            resolution=resolution,
            reference_image=reference_image
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
        
        # 1. 优先从 kwargs 获取视频文件
        video_file = kwargs.get("video_file")
        video_filename = kwargs.get("video_filename")
        
        # 2. 获取视频路径（URL或本地路径）
        video_path = kwargs.get("video_path")
        
        # 3. 从 entities 获取
        if not video_path:
            video_path = entities.get("video_url") or entities.get("url")
        
        # 4. 从用户输入中提取 URL
        if not video_path:
            # 匹配 http:// 或 https:// 开头的 URL
            url_pattern = r'https?://[^\s]+'
            urls = re.findall(url_pattern, user_input)
            if urls:
                video_path = urls[0]
        
        # 5. 检查是否有视频数据
        if not video_file and not video_path:
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
        
        # 6. 使用上传的视频文件或URL
        actual_video_path = video_file if video_file else video_path
        print(f"[调度器] 分析视频 - 类型: {'base64文件' if video_file else 'URL/路径'}")
        print(f"[调度器] 分析视频 - 文件名: {video_filename}")
        
        analyzer = self.tools["video_analyzer"]
        
        # 调用分析工具，传递所有参数
        result = await analyzer.describe_video(
            video_path=actual_video_path,
            video_file=video_file,
            video_filename=video_filename
        )
        
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
        try:
            # 获取对话历史作为上下文
            history = self._get_context_for_intent_recognition()
            
            # 构建对话消息
            messages = []
            
            # 添加系统提示
            messages.append({
                "role": "system",
                "content": "你是一个友好的AI助手，可以进行日常对话。如果用户询问视频或图片生成相关的问题，请引导他们使用相应的功能。"
            })
            
            # 添加历史对话（最近几条）
            for msg in history[-6:]:  # 只取最近6条避免太长
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # 添加当前用户输入
            messages.append({
                "role": "user", 
                "content": user_input
            })
            
            # 调用LLM
            from agent.api.common import load_config
            import aiohttp
            import json
            
            config = load_config()
            text_llm_config = config.get("textLLM", {})
            
            if not text_llm_config:
                return {
                    "success": False,
                    "message": "对话功能未配置，请联系管理员。"
                }
            
            api_key = text_llm_config.get("apiKey", "")
            base_url = text_llm_config.get("baseUrl", "")
            model = text_llm_config.get("model", "gpt-4o")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        assistant_reply = result.get("choices", [{}])[0].get("message", {}).get("content", "抱歉，我无法理解您的问题。")
                        
                        return {
                            "success": True,
                            "message": assistant_reply
                        }
                    else:
                        error_text = await response.text()
                        print(f"[聊天] LLM API调用失败: {response.status} - {error_text}")
                        return {
                            "success": False,
                            "message": "对话服务暂时不可用，请稍后再试。"
                        }
                        
        except Exception as e:
            print(f"[聊天] 处理对话时出错: {e}")
            return {
                "success": False,
                "message": "对话处理出错，请稍后再试。"
            }
    
    
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
    
    def _extract_params_from_input(self, user_input: str, required_params: List[str], **kwargs) -> Dict[str, Any]:
        """
        从用户输入中提取参数（Reaction 架构）
        
        Args:
            user_input: 用户输入
            required_params: 需要的参数列表
            **kwargs: 额外的参数（包括视频文件）
        
        Returns:
            提取到的参数字典
        """
        import re
        extracted = {}
        
        for param in required_params:
            if param == "video_path" or param == "video_url":
                # 优先使用上传的视频文件
                if kwargs.get("video_file"):
                    extracted["video_path"] = kwargs["video_file"]
                    print(f"[参数提取] 使用上传的视频文件")
                else:
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

