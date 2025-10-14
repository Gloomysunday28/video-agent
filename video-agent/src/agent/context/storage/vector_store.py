"""
向量存储
使用简单的向量相似度检索实现上下文检索
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib
from pathlib import Path


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
    
    def __init__(self, persist_path: Optional[str] = None):
        """
        初始化向量存储
        
        Args:
            persist_path: 持久化路径，为None则不持久化
        """
        self.items: List[ContextItem] = []
        self.persist_path = Path(persist_path) if persist_path else None
        
        if self.persist_path and self.persist_path.exists():
            self.load()
    
    def _generate_id(self, content: str) -> str:
        """生成内容ID"""
        return hashlib.md5(content.encode()).hexdigest()
    
    def _compute_embedding(self, text: str) -> List[float]:
        """
        计算文本嵌入（简化版，实际可以接入OpenAI等）
        这里使用简单的字符频率作为特征向量
        """
        # TODO: 接入真实的embedding模型
        # 暂时使用简单的字符频率向量
        char_freq = {}
        for char in text.lower():
            char_freq[char] = char_freq.get(char, 0) + 1
        
        # 转换为固定长度向量（取前100个最常见字符）
        all_chars = sorted(char_freq.items(), key=lambda x: x[1], reverse=True)[:100]
        embedding = [freq for _, freq in all_chars]
        
        # 归一化
        if embedding:
            max_freq = max(embedding)
            embedding = [f / max_freq for f in embedding]
        
        # 补齐到固定长度
        while len(embedding) < 100:
            embedding.append(0.0)
        
        return embedding[:100]
    
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

