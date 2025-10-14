"""
摘要压缩器
使用LLM或规则进行文本摘要
"""

from typing import Optional
import httpx
import asyncio


class Summarizer:
    """
    摘要压缩器
    支持基于LLM的摘要和基于规则的摘要
    """
    
    def __init__(
        self,
        llm_api_url: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        llm_model: str = "gpt-3.5-turbo"
    ):
        """
        初始化摘要器
        
        Args:
            llm_api_url: LLM API地址
            llm_api_key: LLM API密钥
            llm_model: 模型名称
        """
        self.llm_api_url = llm_api_url
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
    
    async def summarize_with_llm(
        self,
        text: str,
        max_length: int = 500,
        language: str = "zh"
    ) -> str:
        """
        使用LLM进行摘要
        
        Args:
            text: 原文本
            max_length: 最大摘要长度
            language: 语言 (zh/en)
        
        Returns:
            摘要文本
        """
        if not self.llm_api_url or not self.llm_api_key:
            raise ValueError("LLM API未配置")
        
        prompt = f"""请将以下文本压缩为{max_length}字以内的摘要，保留关键信息：

{text}

摘要："""
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.llm_api_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.llm_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.llm_model,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": max_length * 2,
                        "temperature": 0.3
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    summary = result["choices"][0]["message"]["content"]
                    return summary.strip()
                else:
                    raise Exception(f"LLM API错误: {response.status_code}")
                    
        except Exception as e:
            print(f"LLM摘要失败: {e}")
            # 降级到规则摘要
            return self.summarize_with_rules(text, max_length)
    
    def summarize_with_rules(
        self,
        text: str,
        max_length: int = 500
    ) -> str:
        """
        基于规则的摘要（不依赖LLM）
        
        Args:
            text: 原文本
            max_length: 最大长度
        
        Returns:
            摘要文本
        """
        from agent.context.compression.keyword_extractor import KeywordExtractor
        
        if len(text) <= max_length:
            return text
        
        extractor = KeywordExtractor()
        
        # 提取关键句
        num_sentences = max(1, max_length // 100)  # 假设每句100字
        key_sentences = extractor.extract_key_sentences(
            text,
            top_k=num_sentences,
            max_length=150
        )
        
        summary = " ".join(key_sentences)
        
        # 如果还是太长，提取关键词
        if len(summary) > max_length:
            keywords = extractor.extract_keywords(text, top_k=20)
            summary = "关键内容: " + ", ".join([kw for kw, _ in keywords[:10]])
        
        return summary[:max_length]
    
    async def progressive_compress(
        self,
        text: str,
        target_length: int,
        use_llm: bool = False
    ) -> str:
        """
        渐进式压缩
        如果原文本过长，分段压缩后再合并
        
        Args:
            text: 原文本
            target_length: 目标长度
            use_llm: 是否使用LLM
        
        Returns:
            压缩后的文本
        """
        if len(text) <= target_length:
            return text
        
        # 如果文本非常长，先分段压缩
        chunk_size = 5000
        if len(text) > chunk_size:
            chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
            compressed_chunks = []
            
            chunk_target = target_length // len(chunks)
            
            for chunk in chunks:
                if use_llm:
                    compressed = await self.summarize_with_llm(chunk, chunk_target)
                else:
                    compressed = self.summarize_with_rules(chunk, chunk_target)
                compressed_chunks.append(compressed)
            
            text = "\n\n".join(compressed_chunks)
        
        # 最后再压缩一次到目标长度
        if use_llm:
            return await self.summarize_with_llm(text, target_length)
        else:
            return self.summarize_with_rules(text, target_length)

