"""
向量存储
使用简单的向量相似度检索实现上下文检索
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib
from pathlib import Path
import httpx
import asyncio


@dataclass
class ContextItem:
    """上下文项"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    timestamp: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class VectorStore:
    """
    向量存储
    支持向量检索和关键词检索
    """
    
    def __init__(
        self, 
        persist_path: Optional[str] = None,
        embedding_api_url: Optional[str] = None,
        embedding_api_key: Optional[str] = None,
        embedding_model: str = "text-embedding-ada-002"
    ):
        """
        初始化向量存储
        
        Args:
            persist_path: 持久化路径，为None则不持久化
            embedding_api_url: Embedding API URL
            embedding_api_key: Embedding API Key
            embedding_model: Embedding 模型名称
        """
        self.items: List[ContextItem] = []
        self.persist_path = Path(persist_path) if persist_path else None
        self.embedding_api_url = embedding_api_url
        self.embedding_api_key = embedding_api_key
        self.embedding_model = embedding_model
        self.use_api_embedding = bool(embedding_api_url and embedding_api_key)
        
        if self.use_api_embedding:
            print(f"[向量存储] 使用 API Embedding: {embedding_model}")
        else:
            print(f"[向量存储] 使用简化版 Embedding（字符频率）")
        
        if self.persist_path and self.persist_path.exists():
            self.load()
            print(f"[向量存储] 从 {self.persist_path} 加载了 {len(self.items)} 条记录")
    
    def _generate_id(self, content: str) -> str:
        """生成内容ID"""
        return hashlib.md5(content.encode()).hexdigest()
    
    async def _compute_embedding_api(self, text: str) -> List[float]:
        """使用 API 计算文本嵌入"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.embedding_api_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.embedding_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.embedding_model,
                        "input": text
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result["data"][0]["embedding"]
        except Exception as e:
            print(f"[向量存储] API Embedding 失败: {e}，降级使用简化版")
            return self._compute_embedding_simple(text)
    
    def _compute_embedding_simple(self, text: str) -> List[float]:
        """
        计算文本嵌入（优化版）
        使用词频、字符频率和文本特征的组合
        """
        import re
        
        # 1. 词频统计
        words = re.findall(r'\b\w+\b', text.lower())
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # 2. 字符频率统计
        char_freq = {}
        for char in text.lower():
            if char.isalnum() or char.isspace():
                char_freq[char] = char_freq.get(char, 0) + 1
        
        # 3. 文本特征
        text_features = [
            len(text),  # 文本长度
            len(words),  # 词数
            len(set(words)) if words else 0,  # 唯一词数
            text.count('?'),  # 问号数量
            text.count('!'),  # 感叹号数量
            text.count('.'),  # 句号数量
            sum(1 for c in text if c.isupper()),  # 大写字母数量
            sum(1 for c in text if c.isdigit()),  # 数字数量
        ]
        
        # 4. 组合特征向量
        embedding = []
        
        # 添加标准化的文本特征 (8维)
        max_feature = max(text_features) if text_features and max(text_features) > 0 else 1
        embedding.extend([f / max_feature for f in text_features])
        
        # 添加前30个最常见词的频率 (30维)
        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:30]
        word_freqs = [freq for _, freq in top_words]
        if word_freqs:
            max_word_freq = max(word_freqs)
            embedding.extend([f / max_word_freq for f in word_freqs])
        
        # 添加前62个最常见字符的频率 (62维，总共100维)
        remaining_dims = 100 - len(embedding)
        top_chars = sorted(char_freq.items(), key=lambda x: x[1], reverse=True)[:remaining_dims]
        char_freqs = [freq for _, freq in top_chars]
        if char_freqs:
            max_char_freq = max(char_freqs)
            embedding.extend([f / max_char_freq for f in char_freqs])
        
        # 确保向量长度为100
        while len(embedding) < 100:
            embedding.append(0.0)
        
        return embedding[:100]
    
    def _compute_embedding(self, text: str) -> List[float]:
        """
        计算文本嵌入（同步包装）
        """
        if self.use_api_embedding:
            # 在同步上下文中运行异步函数
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果已经在事件循环中，创建一个任务
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, self._compute_embedding_api(text))
                        return future.result(timeout=30)
                else:
                    return loop.run_until_complete(self._compute_embedding_api(text))
            except Exception as e:
                print(f"[向量存储] 异步调用失败: {e}，使用简化版")
                return self._compute_embedding_simple(text)
        else:
            return self._compute_embedding_simple(text)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2:
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def add(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None
    ) -> str:
        """
        添加上下文
        
        Args:
            content: 上下文内容
            metadata: 元数据
            embedding: 预计算的embedding，为None则自动计算
        
        Returns:
            item_id: 生成的ID
        """
        import time
        
        item_id = self._generate_id(content)
        
        # 检查是否已存在
        for item in self.items:
            if item.id == item_id:
                return item_id
        
        # 计算embedding
        if embedding is None:
            embedding = self._compute_embedding(content)
        
        item = ContextItem(
            id=item_id,
            content=content,
            metadata=metadata or {},
            embedding=embedding,
            timestamp=time.time()
        )
        
        self.items.append(item)
        
        if self.persist_path:
            self.save()
        
        return item_id
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.0
    ) -> List[Tuple[ContextItem, float]]:
        """
        向量检索
        
        Args:
            query: 查询文本
            top_k: 返回top-k结果
            threshold: 相似度阈值
        
        Returns:
            [(item, score), ...] 按相似度降序排列
        """
        query_embedding = self._compute_embedding(query)
        
        results = []
        for item in self.items:
            if item.embedding:
                score = self._cosine_similarity(query_embedding, item.embedding)
                if score >= threshold:
                    results.append((item, score))
        
        # 按分数降序排序
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
    
    def get(self, item_id: str) -> Optional[ContextItem]:
        """根据ID获取项"""
        for item in self.items:
            if item.id == item_id:
                return item
        return None
    
    def delete(self, item_id: str) -> bool:
        """删除项"""
        for i, item in enumerate(self.items):
            if item.id == item_id:
                self.items.pop(i)
                if self.persist_path:
                    self.save()
                return True
        return False
    
    def clear(self):
        """清空所有数据"""
        self.items.clear()
        if self.persist_path:
            self.save()
    
    def get_all(self) -> List[ContextItem]:
        """获取所有项"""
        return self.items.copy()
    
    def save(self):
        """持久化到文件"""
        if not self.persist_path:
            return
        
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "items": [item.to_dict() for item in self.items]
        }
        
        with open(self.persist_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[向量存储] 已保存 {len(self.items)} 条记录到 {self.persist_path}")
    
    def load(self):
        """从文件加载"""
        if not self.persist_path or not self.persist_path.exists():
            return
        
        with open(self.persist_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.items = [
            ContextItem(**item_dict)
            for item_dict in data.get("items", [])
        ]
    
    def __len__(self) -> int:
        """返回存储的项数"""
        return len(self.items)

