"""
API 公共工具和基类
"""

import uuid
from typing import Optional, Dict, Any, Callable
from pathlib import Path
import yaml
from fastapi import HTTPException

from agent.core import AgentScheduler
from agent.tools.generate import JianyingConfig


def generate_session_id() -> str:
    """生成会话ID"""
    return str(uuid.uuid4())


def get_scheduler(
    session_id: str,
    use_llm_intent: bool = False,
    context_compression_threshold: int = 10000
) -> AgentScheduler:
    """
    获取调度器实例
    
    Args:
        session_id: 会话ID
        use_llm_intent: 是否使用LLM进行意图识别
        context_compression_threshold: 上下文压缩阈值（默认10000字符）
    
    Returns:
        AgentScheduler实例
    """
    return AgentScheduler(
        session_id=session_id,
        use_llm_intent=use_llm_intent,
        context_compression_threshold=context_compression_threshold
    )


def load_config(config_name: str = "index.yml") -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        config_name: 配置文件名
    
    Returns:
        配置字典
    """
    config_path = Path(__file__).parent.parent / "config" / config_name
    
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def load_jianying_config() -> JianyingConfig:
    """
    加载剪映API配置
    
    Returns:
        JianyingConfig实例
    """
    config = load_config()
    jianying_cfg = config.get("jianyingAPI", {})
    
    if not jianying_cfg:
        raise ValueError("剪映API未配置")
    
    return JianyingConfig(
        web_id=jianying_cfg.get("webId", ""),
        ms_token=jianying_cfg.get("msToken", ""),
        generate_sign=jianying_cfg.get("generateSign", ""),
        status_sign=jianying_cfg.get("statusSign", ""),
        generate_a_bogus=jianying_cfg.get("generateABogus", ""),
        status_a_bogus=jianying_cfg.get("statusABogus", ""),
        cookies=jianying_cfg.get("cookies", {})
    )


async def execute_with_scheduler(
    session_id: str,
    user_input: str,
    use_llm_intent: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    使用调度器执行任务（公共封装）
    
    Args:
        session_id: 会话ID
        user_input: 用户输入
        use_llm_intent: 是否使用LLM意图识别
        **kwargs: 额外参数传递给调度器
    
    Returns:
        执行结果（已包含session_id）
    """
    try:
        # 创建调度器
        scheduler = get_scheduler(
            session_id=session_id,
            use_llm_intent=use_llm_intent
        )
        
        # 执行任务
        result = await scheduler.process(user_input, **kwargs)
        
        # 添加会话ID到返回结果
        return {
            **result,
            "session_id": session_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def handle_api_error(error: Exception, default_status_code: int = 500) -> HTTPException:
    """
    统一错误处理
    
    Args:
        error: 异常对象
        default_status_code: 默认HTTP状态码
    
    Returns:
        HTTPException
    """
    if isinstance(error, HTTPException):
        return error
    
    # 根据异常类型返回不同的状态码
    if isinstance(error, ValueError):
        return HTTPException(status_code=400, detail=str(error))
    elif isinstance(error, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    elif isinstance(error, PermissionError):
        return HTTPException(status_code=403, detail=str(error))
    else:
        return HTTPException(status_code=default_status_code, detail=str(error))


class APIResponse:
    """API 响应封装"""
    
    @staticmethod
    def success(data: Any, message: str = "成功") -> Dict[str, Any]:
        """
        成功响应
        
        Args:
            data: 响应数据
            message: 消息
        
        Returns:
            标准响应格式
        """
        return {
            "success": True,
            "message": message,
            "data": data
        }
    
    @staticmethod
    def error(message: str, code: Optional[str] = None, details: Any = None) -> Dict[str, Any]:
        """
        错误响应
        
        Args:
            message: 错误消息
            code: 错误代码
            details: 错误详情
        
        Returns:
            标准错误格式
        """
        response = {
            "success": False,
            "message": message
        }
        
        if code:
            response["code"] = code
        
        if details:
            response["details"] = details
        
        return response

