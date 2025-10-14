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
        
        # 设置持久化路径
        if vector_store_path is None:
            vector_store_path = str(DEFAULT_DATA_DIR / f"vector_store_{session_id}.json")
        
        # 初始化存储
        self.memory_store = MemoryStore(max_tokens=max_context_length)
        self.vector_store = VectorStore(persist_path=vector_store_path)
        
        # 初始化压缩工具
        self.keyword_extractor = KeywordExtractor()
        self.summarizer = Summarizer(
            llm_api_url=llm_api_url,
            llm_api_key=llm_api_key
        )
        
        # 压缩历史
        self.compression_history: List[Dict[str, Any]] = []
    
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
        # 添加到内存存储
        self.memory_store.add_message(role, content, metadata)
        
        # 检查是否需要压缩
        total_length = self.memory_store.get_total_tokens()
        if total_length > self.auto_compress_threshold:
            self._auto_compress()
    
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
        return self.vector_store.add(content, metadata)
    
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
        
        return compression_info
    
    def _auto_compress(self):
        """自动触发压缩"""
        print(f"⚠️  上下文长度超过阈值 {self.auto_compress_threshold}，自动压缩中...")
        
        result = self.compress_context(use_llm=False, target_ratio=0.3)
        
        print(f"✅ 压缩完成: {result['original_length']} -> {result['compressed_length']} "
              f"(压缩率: {result['ratio']:.2%})")
    
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

