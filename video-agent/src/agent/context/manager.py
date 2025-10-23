"""
上下文管理器（调度器）
统一管理上下文的存储、检索、压缩
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from agent.context.storage.vector_store import VectorStore
from agent.context.storage.memory_store import MemoryStore
from agent.context.compression.keyword_extractor import KeywordExtractor
from agent.context.compression.summarizer import Summarizer

# 默认持久化目录
DEFAULT_DATA_DIR = Path(__file__).parent / "data"


class ContextManager:
    """
    上下文管理器
    
    职责：
    1. 管理对话历史（短期记忆）
    2. 管理长期记忆（向量存储）
    3. 自动触发压缩（>50k时）
    4. 智能检索相关上下文
    """
    
    def __init__(
        self,
        max_context_length: int = 50000,
        auto_compress_threshold: int = 50000,
        vector_store_path: Optional[str] = None,
        llm_api_url: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        session_id: str = "default"
    ):
        """
        初始化上下文管理器
        
        Args:
            max_context_length: 最大上下文长度
            auto_compress_threshold: 自动压缩阈值（字符数）
            vector_store_path: 向量存储持久化路径，为None则使用默认路径
            llm_api_url: LLM API地址（用于摘要）
            llm_api_key: LLM API密钥
            session_id: 会话ID，用于区分不同的会话
        """
        self.max_context_length = max_context_length
        self.auto_compress_threshold = auto_compress_threshold
        self.session_id = session_id
        
        # 确保数据目录存在
        DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # 为每个会话创建独立的子目录
        self.session_data_dir = DEFAULT_DATA_DIR / session_id
        self.session_data_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置持久化路径
        if vector_store_path is None:
            vector_store_path = str(self.session_data_dir / "vector_store.json")
        
        # 初始化存储
        self.memory_store = MemoryStore(max_tokens=max_context_length)
        self.vector_store = VectorStore(
            persist_path=vector_store_path,
            # 禁用API embedding，直接使用简化版
            embedding_api_url=None,
            embedding_api_key=None,
            embedding_model="simple"
        )
        
        # 初始化压缩工具
        self.keyword_extractor = KeywordExtractor()
        self.summarizer = Summarizer(
            llm_api_url=llm_api_url,
            llm_api_key=llm_api_key
        )
        
        # 意图识别器（用于压缩时的智能分析）
        self.intent_recognizer = None
        
        # 压缩历史
        self.compression_history: List[Dict[str, Any]] = []
        
        # 压缩阈值
        self.compression_threshold = auto_compress_threshold
        
        # Reaction 架构：待处理任务状态
        self.pending_task: Optional[Dict[str, Any]] = None
        
        # 初始化会话时创建向量存储文件（即使是空的）
        print(f"[上下文管理器] 初始化会话: {session_id}")
        self.vector_store.save()  # 确保文件存在
        
        # 创建会话元数据文件
        self._save_session_metadata()
    
    def _save_session_metadata(self):
        """保存会话元数据"""
        import time
        import json
        
        metadata_path = self.session_data_dir / "metadata.json"
        
        # 如果文件已存在，加载并更新
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            metadata["last_updated"] = time.time()
            metadata["message_count"] = metadata.get("message_count", 0)
        else:
            # 创建新的元数据
            metadata = {
                "session_id": self.session_id,
                "created_at": time.time(),
                "last_updated": time.time(),
                "message_count": 0,
                "compression_count": 0
            }
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"[上下文管理器] 会话元数据已保存: {metadata_path}")
    
    def _update_session_metadata(self, message_count: int = 0, compression_count: int = 0):
        """更新会话元数据"""
        import time
        import json
        
        metadata_path = self.session_data_dir / "metadata.json"
        
        # 加载现有元数据
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            metadata = {
                "session_id": self.session_id,
                "created_at": time.time(),
                "message_count": 0,
                "compression_count": 0
            }
        
        # 更新计数
        metadata["last_updated"] = time.time()
        metadata["message_count"] = metadata.get("message_count", 0) + message_count
        metadata["compression_count"] = metadata.get("compression_count", 0) + compression_count
        metadata["total_vector_items"] = len(self.vector_store)
        
        # 保存
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def set_intent_recognizer(self, recognizer):
        """
        设置意图识别器（用于智能压缩）
        
        Args:
            recognizer: IntentRecognizer实例
        """
        self.intent_recognizer = recognizer
        # 只在初始化时打印一次
        if not hasattr(self, '_intent_recognizer_initialized'):
            print("[上下文管理器] 已启用意图识别增强压缩")
            self._intent_recognizer_initialized = True
    
    def set_pending_task(self, task_type: str, required_params: List[str], context: Optional[Dict[str, Any]] = None):
        """
        设置待处理任务（Reaction 架构）
        
        Args:
            task_type: 任务类型（如 "analyze_video"）
            required_params: 需要的参数列表
            context: 任务上下文
        """
        self.pending_task = {
            "type": task_type,
            "required_params": required_params,
            "context": context or {},
            "timestamp": self._get_timestamp()
        }
        print(f"[上下文管理器] 设置待处理任务: {task_type}, 需要参数: {required_params}")
    
    def get_pending_task(self) -> Optional[Dict[str, Any]]:
        """获取待处理任务"""
        return self.pending_task
    
    def clear_pending_task(self):
        """清除待处理任务"""
        if self.pending_task:
            print(f"[上下文管理器] 清除待处理任务: {self.pending_task['type']}")
        self.pending_task = None
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        添加消息
        
        Args:
            role: 角色 (user/assistant/system)
            content: 内容
            metadata: 元数据
        """
        import time
        
        # 添加到内存存储
        self.memory_store.add_message(role, content, metadata)
        
        # 同时保存到向量存储（长期记忆）
        message_content = f"[{role}] {content}"
        message_metadata = {
            "role": role,
            "timestamp": time.time(),
            "session_id": self.session_id,
            **(metadata or {})
        }
        self.vector_store.add(message_content, message_metadata)
        print(f"[上下文管理器] 消息已保存 - {role}: {content[:50]}{'...' if len(content) > 50 else ''}")
        
        # 更新会话元数据
        self._update_session_metadata(message_count=1)
        
        # 检查是否需要压缩
        total_length = self.memory_store.get_total_tokens()
        if total_length > self.auto_compress_threshold:
            print(f"[上下文管理器] 上下文长度 {total_length} 超过阈值 {self.auto_compress_threshold}，准备自动压缩")
            import asyncio
            asyncio.create_task(self._auto_compress_async())
    
    def get_context(
        self,
        query: Optional[str] = None,
        max_length: Optional[int] = None,
        include_vector_search: bool = True,
        top_k_similar: int = 3
    ) -> str:
        """
        获取上下文
        
        Args:
            query: 查询文本（用于检索相关上下文）
            max_length: 最大长度
            include_vector_search: 是否包含向量检索的长期记忆
            top_k_similar: 检索top-k相似内容
        
        Returns:
            拼接好的上下文字符串
        """
        contexts = []
        
        # 1. 获取短期记忆（对话历史）
        short_term = self.memory_store.get_context_string(
            max_tokens=max_length // 2 if max_length else None
        )
        if short_term:
            contexts.append("## 对话历史\n" + short_term)
        
        # 2. 如果有查询，检索长期记忆
        if query and include_vector_search:
            similar_items = self.vector_store.search(query, top_k=top_k_similar)
            if similar_items:
                long_term_parts = []
                for item, score in similar_items:
                    long_term_parts.append(f"[相关度: {score:.2f}] {item.content}")
                long_term = "\n\n".join(long_term_parts)
                contexts.append("## 相关记忆\n" + long_term)
        
        # 3. 拼接所有上下文
        full_context = "\n\n---\n\n".join(contexts)
        
        # 4. 如果超过长度限制，压缩
        if max_length and len(full_context) > max_length:
            full_context = self.summarizer.summarize_with_rules(
                full_context,
                max_length=max_length
            )
        
        return full_context
    
    def save_to_long_term(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        保存到长期记忆（向量存储）
        
        Args:
            content: 内容
            metadata: 元数据
        
        Returns:
            item_id
        """
        print(f"[上下文管理器] 保存到长期记忆，内容长度: {len(content)} 字符")
        item_id = self.vector_store.add(content, metadata)
        print(f"[上下文管理器] ✓ 已保存，ID: {item_id[:8]}..., 当前向量存储共 {len(self.vector_store)} 条")
        return item_id
    
    def search_long_term(
        self,
        query: str,
        top_k: int = 5
    ) -> List[str]:
        """
        检索长期记忆
        
        Args:
            query: 查询
            top_k: 返回top-k结果
        
        Returns:
            检索结果列表
        """
        results = self.vector_store.search(query, top_k=top_k)
        return [item.content for item, score in results]
    
    def compress_context(
        self,
        use_llm: bool = False,
        target_ratio: float = 0.5
    ) -> Dict[str, Any]:
        """
        手动压缩当前上下文
        
        Args:
            use_llm: 是否使用LLM压缩
            target_ratio: 目标压缩比
        
        Returns:
            压缩信息
        """
        # 获取当前上下文
        current_context = self.memory_store.get_context_string()
        original_length = len(current_context)
        
        if original_length == 0:
            return {"status": "empty", "original_length": 0, "compressed_length": 0}
        
        # 压缩
        target_length = int(original_length * target_ratio)
        
        if use_llm:
            import asyncio
            compressed = asyncio.run(
                self.summarizer.progressive_compress(
                    current_context,
                    target_length,
                    use_llm=True
                )
            )
        else:
            compressed = self.summarizer.summarize_with_rules(
                current_context,
                max_length=target_length
            )
        
        # 保存压缩结果到长期记忆
        self.save_to_long_term(
            compressed,
            metadata={"type": "compressed", "original_length": original_length}
        )
        
        # 清空短期记忆
        self.memory_store.clear()
        
        # 将压缩结果作为system消息添加回去
        self.memory_store.add_message(
            role="system",
            content=f"[已压缩的历史上下文]\n{compressed}",
            metadata={"compressed": True}
        )
        
        compression_info = {
            "status": "success",
            "original_length": original_length,
            "compressed_length": len(compressed),
            "ratio": len(compressed) / original_length if original_length > 0 else 0
        }
        
        self.compression_history.append(compression_info)
        
        # 更新会话元数据
        self._update_session_metadata(compression_count=1)
        
        return compression_info
    
    async def _auto_compress_async(self):
        """
        自动触发压缩（异步版本，支持意图识别）
        """
        print(f"⚠️  上下文长度超过阈值 {self.auto_compress_threshold}，自动压缩中...")
        
        # 如果有意图识别器，使用智能压缩
        if self.intent_recognizer:
            result = await self._intent_aware_compress()
        else:
            result = self.compress_context(use_llm=False, target_ratio=0.3)
        
        print(f"✅ 压缩完成: {result['original_length']} -> {result['compressed_length']} "
              f"(压缩率: {result['ratio']:.2%})")
    
    def _auto_compress(self):
        """自动触发压缩（同步版本）"""
        print(f"⚠️  上下文长度超过阈值 {self.auto_compress_threshold}，自动压缩中...")
        result = self.compress_context(use_llm=False, target_ratio=0.3)
        print(f"✅ 压缩完成: {result['original_length']} -> {result['compressed_length']} "
              f"(压缩率: {result['ratio']:.2%})")
    
    async def _intent_aware_compress(self) -> Dict[str, Any]:
        """
        基于意图识别的智能压缩
        
        策略：
        1. 对每条消息进行意图识别
        2. 重要意图（生成视频、分析视频）的消息保留更多细节
        3. 普通聊天消息可以更激进地压缩
        4. 将不同意图的内容分别保存到长期记忆
        """
        messages = self.memory_store.get_history()
        
        if not messages:
            return {"status": "empty", "original_length": 0, "compressed_length": 0}
        
        # 按意图分类消息
        intent_groups = {
            "important": [],  # 重要意图（视频生成、分析等）
            "normal": [],     # 普通聊天
            "system": []      # 系统消息
        }
        
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")
            
            if role == "system":
                intent_groups["system"].append(msg)
                continue
            
            # 识别意图
            intent_result = self.intent_recognizer.recognize_sync(content)
            intent_type = intent_result["intent"]
            
            # 分类
            if intent_type.value in ["generate_video", "analyze_video", "edit_video"]:
                intent_groups["important"].append({
                    **msg,
                    "intent": intent_type.value
                })
            else:
                intent_groups["normal"].append({
                    **msg,
                    "intent": intent_type.value
                })
        
        print(f"[智能压缩] 重要消息: {len(intent_groups['important'])}, "
              f"普通消息: {len(intent_groups['normal'])}, "
              f"系统消息: {len(intent_groups['system'])}")
        
        # 分别压缩
        compressed_parts = []
        original_length = 0
        
        # 1. 重要消息：保留更多细节（压缩比50%）
        if intent_groups["important"]:
            important_text = "\n\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in intent_groups["important"]
            ])
            original_length += len(important_text)
            
            compressed_important = self.summarizer.summarize_with_rules(
                important_text,
                max_length=int(len(important_text) * 0.5)
            )
            
            # 保存到长期记忆
            self.save_to_long_term(
                compressed_important,
                metadata={"type": "important_compressed", "intent_count": len(intent_groups["important"])}
            )
            
            compressed_parts.append(f"[重要对话记录]\n{compressed_important}")
        
        # 2. 普通消息：更激进压缩（压缩比20%）
        if intent_groups["normal"]:
            normal_text = "\n\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in intent_groups["normal"]
            ])
            original_length += len(normal_text)
            
            # 提取关键词代替完整内容
            keywords = self.keyword_extractor.extract_keywords(normal_text, num_keywords=10)
            compressed_normal = f"普通对话关键词: {', '.join(keywords)}"
            
            # 保存到长期记忆
            self.save_to_long_term(
                compressed_normal,
                metadata={"type": "normal_compressed", "message_count": len(intent_groups["normal"])}
            )
            
            compressed_parts.append(f"[普通对话摘要]\n{compressed_normal}")
        
        # 3. 系统消息：保留最新的几条
        if intent_groups["system"]:
            recent_system = intent_groups["system"][-3:]  # 只保留最近3条
            system_text = "\n".join([msg['content'] for msg in recent_system])
            compressed_parts.append(f"[系统消息]\n{system_text}")
        
        # 合并压缩结果
        compressed = "\n\n---\n\n".join(compressed_parts)
        
        # 清空短期记忆
        self.memory_store.clear()
        
        # 将压缩结果作为system消息添加回去
        self.memory_store.add_message(
            role="system",
            content=compressed,
            metadata={"compressed": True, "intent_aware": True}
        )
        
        compression_info = {
            "status": "success",
            "method": "intent_aware",
            "original_length": original_length,
            "compressed_length": len(compressed),
            "ratio": len(compressed) / original_length if original_length > 0 else 0,
            "intent_distribution": {
                "important": len(intent_groups["important"]),
                "normal": len(intent_groups["normal"]),
                "system": len(intent_groups["system"])
            }
        }
        
        self.compression_history.append(compression_info)
        
        return compression_info
    
    def get_full_context(self) -> str:
        """
        获取完整上下文字符串
        
        Returns:
            完整上下文文本
        """
        return self.memory_store.get_context_string()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "short_term_messages": len(self.memory_store),
            "short_term_tokens": self.memory_store.get_total_tokens(),
            "long_term_items": len(self.vector_store),
            "compression_count": len(self.compression_history),
            "auto_compress_threshold": self.auto_compress_threshold
        }
    
    def clear(self, include_long_term: bool = False):
        """
        清空上下文
        
        Args:
            include_long_term: 是否同时清空长期记忆
        """
        self.memory_store.clear()
        if include_long_term:
            self.vector_store.clear()
        self.compression_history.clear()

