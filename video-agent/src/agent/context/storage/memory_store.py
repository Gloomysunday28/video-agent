"""
内存存储
按时间序列存储对话上下文
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from collections import deque
import time


@dataclass
class Message:
    """消息"""
    role: str  # user, assistant, system
    content: str
    timestamp: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def __len__(self) -> int:
        """返回内容长度"""
        return len(self.content)


class MemoryStore:
    """
    内存存储
    使用滑动窗口管理对话历史
    """
    
    def __init__(self, max_messages: int = 100, max_tokens: int = 50000):
        """
        初始化内存存储
        
        Args:
            max_messages: 最大消息数
            max_tokens: 最大token数（这里简化为字符数）
        """
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.messages: deque = deque(maxlen=max_messages)
    
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
        message = Message(
            role=role,
            content=content,
            timestamp=time.time(),
            metadata=metadata or {}
        )
        
        self.messages.append(message)
        
        # 检查是否超过token限制
        self._trim_by_tokens()
    
    def _trim_by_tokens(self):
        """根据token数修剪"""
        total_tokens = sum(len(msg.content) for msg in self.messages)
        
        # 如果超过限制，删除最旧的消息
        while total_tokens > self.max_tokens and len(self.messages) > 1:
            removed = self.messages.popleft()
            total_tokens -= len(removed.content)
    
    def get_messages(
        self,
        last_n: Optional[int] = None,
        max_tokens: Optional[int] = None,
        role_filter: Optional[str] = None
    ) -> List[Message]:
        """
        获取消息
        
        Args:
            last_n: 获取最后N条消息
            max_tokens: 最大token数
            role_filter: 角色过滤 (user/assistant/system)
        
        Returns:
            消息列表
        """
        messages = list(self.messages)
        
        # 角色过滤
        if role_filter:
            messages = [msg for msg in messages if msg.role == role_filter]
        
        # 取最后N条
        if last_n:
            messages = messages[-last_n:]
        
        # Token限制
        if max_tokens:
            result = []
            total_tokens = 0
            for msg in reversed(messages):
                msg_len = len(msg.content)
                if total_tokens + msg_len <= max_tokens:
                    result.insert(0, msg)
                    total_tokens += msg_len
                else:
                    break
            messages = result
        
        return messages
    
    def get_context_string(
        self,
        last_n: Optional[int] = None,
        max_tokens: Optional[int] = None,
        include_roles: bool = True
    ) -> str:
        """
        获取上下文字符串
        
        Args:
            last_n: 最后N条
            max_tokens: 最大token数
            include_roles: 是否包含角色标识
        
        Returns:
            拼接的上下文字符串
        """
        messages = self.get_messages(last_n=last_n, max_tokens=max_tokens)
        
        if include_roles:
            return "\n\n".join([
                f"{msg.role.upper()}: {msg.content}"
                for msg in messages
            ])
        else:
            return "\n\n".join([msg.content for msg in messages])
    
    def get_history(self) -> List[Dict[str, Any]]:
        """
        获取完整历史（字典格式）
        
        Returns:
            消息字典列表
        """
        return [msg.to_dict() for msg in self.messages]
    
    def clear(self):
        """清空所有消息"""
        self.messages.clear()
    
    def get_total_tokens(self) -> int:
        """获取总token数"""
        return sum(len(msg.content) for msg in self.messages)
    
    def __len__(self) -> int:
        """返回消息数"""
        return len(self.messages)
    
    def get_full_context(self) -> str:
        """获取完整上下文（别名，兼容旧接口）"""
        return self.get_context_string()

