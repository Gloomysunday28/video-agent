"""
关键词提取器
用于从上下文中提取关键词和关键句
"""

from typing import List, Dict, Tuple
import re
from collections import Counter


class KeywordExtractor:
    """
    关键词提取器
    支持多种提取策略
    """
    
    def __init__(self):
        # 中英文停用词
        self.stop_words = {
            # 中文
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
            # 英文
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be', 'been',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
        }
    
    def extract_keywords(
        self,
        text: str,
        top_k: int = 10,
        min_length: int = 2
    ) -> List[Tuple[str, int]]:
        """
        提取关键词
        
        Args:
            text: 文本
            top_k: 返回top-k关键词
            min_length: 最小词长
        
        Returns:
            [(keyword, count), ...] 按频率降序
        """
        # 分词（简化版，实际可以用jieba等）
        words = self._tokenize(text)
        
        # 过滤停用词和短词
        words = [
            w for w in words
            if w.lower() not in self.stop_words and len(w) >= min_length
        ]
        
        # 统计词频
        word_freq = Counter(words)
        
        # 返回top-k
        return word_freq.most_common(top_k)
    
    def extract_key_sentences(
        self,
        text: str,
        top_k: int = 3,
        max_length: int = 200
    ) -> List[str]:
        """
        提取关键句子
        
        Args:
            text: 文本
            top_k: 返回top-k句子
            max_length: 句子最大长度
        
        Returns:
            关键句子列表
        """
        # 分句
        sentences = self._split_sentences(text)
        
        # 过滤过长的句子
        sentences = [s for s in sentences if len(s) <= max_length]
        
        if not sentences:
            return []
        
        # 计算句子重要性（基于关键词）
        keywords = [kw for kw, _ in self.extract_keywords(text, top_k=20)]
        
        sentence_scores = []
        for sent in sentences:
            score = sum(1 for kw in keywords if kw in sent)
            sentence_scores.append((sent, score))
        
        # 按分数排序
        sentence_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 返回top-k
        return [sent for sent, _ in sentence_scores[:top_k]]
    
    def compress_text(
        self,
        text: str,
        target_ratio: float = 0.5,
        strategy: str = "keywords"
    ) -> str:
        """
        压缩文本
        
        Args:
            text: 原文本
            target_ratio: 目标压缩比（0-1）
            strategy: 压缩策略 ("keywords" 或 "sentences")
        
        Returns:
            压缩后的文本
        """
        if strategy == "keywords":
            # 基于关键词压缩
            num_keywords = max(1, int(len(text) * target_ratio / 10))
            keywords = self.extract_keywords(text, top_k=num_keywords)
            return "关键词: " + ", ".join([kw for kw, _ in keywords])
        
        elif strategy == "sentences":
            # 基于关键句压缩
            num_sentences = max(1, int(len(self._split_sentences(text)) * target_ratio))
            key_sentences = self.extract_key_sentences(text, top_k=num_sentences)
            return "\n".join(key_sentences)
        
        return text
    
    def _tokenize(self, text: str) -> List[str]:
        """
        分词（简化版）
        实际使用可以接入jieba或其他分词工具
        """
        # 简单的按空格和标点分词
        # 对中文按字符分（简化处理）
        words = []
        
        # 处理英文单词
        english_words = re.findall(r'[a-zA-Z]+', text)
        words.extend(english_words)
        
        # 处理中文词（这里简化为2-4字的组合）
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]', text)
        for i in range(len(chinese_chars) - 1):
            # 2字词
            words.append(chinese_chars[i] + chinese_chars[i+1])
            # 3字词
            if i < len(chinese_chars) - 2:
                words.append(chinese_chars[i] + chinese_chars[i+1] + chinese_chars[i+2])
        
        return words
    
    def _split_sentences(self, text: str) -> List[str]:
        """分句"""
        # 按句号、问号、叹号分句
        sentences = re.split(r'[。！？!?.]\s*', text)
        # 过滤空句子
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences

