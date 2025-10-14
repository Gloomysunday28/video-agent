# Agent核心调度器

## 架构概览

```
用户输入
   ↓
[调度器 Scheduler]
   ↓
1. 意图识别 (IntentRecognizer)
   ↓
2. 工具调度
   ├─ 视频生成 (JianyingVideoGenerator)
   ├─ 视频分析 (VideoAnalyzer)
   └─ 对话交互 (ChatLLM)
   ↓
3. 上下文管理 (ContextManager)
   ├─ 短期记忆 (MemoryStore)
   ├─ 长期记忆 (VectorStore)
   └─ 智能压缩 (意图感知)
   ↓
返回结果
```

## 核心特性

### 1. 意图驱动调度
- 自动识别用户意图（生成视频、分析视频、聊天等）
- 根据意图调用对应工具
- 支持LLM增强和规则匹配

### 2. 智能上下文管理
- **短期记忆**: 对话历史，自动滑动窗口
- **长期记忆**: 向量存储，支持语义检索
- **自动压缩**: 超过阈值自动触发

### 3. 意图感知压缩 🌟
上下文压缩时根据意图分类：
- **重要意图** (视频生成/分析): 保留50%细节
- **普通聊天**: 激进压缩，提取关键词
- **系统消息**: 保留最近3条

## 使用示例

### 基础使用

```python
from agent.core import AgentScheduler

# 初始化调度器
scheduler = AgentScheduler(
    session_id="user_123",
    use_llm_intent=True,
    context_compression_threshold=50000
)

# 处理用户输入
result = await scheduler.process(
    "帮我生成一个5秒的视频，内容是一只猫在草地上玩耍"
)

print(f"意图: {result['intent']}")
print(f"结果: {result['result']}")
print(f"上下文信息: {result['context_info']}")
```

### 视频分析

```python
result = await scheduler.process(
    "分析这个视频的内容",
    video_path="example.mp4"
)
```

### 查看上下文摘要

```python
summary = scheduler.get_context_summary()
print(summary)
# {
#     "session_id": "user_123",
#     "context_length": 15234,
#     "message_count": 42,
#     "compression_threshold": 50000
# }
```

### 清空上下文

```python
scheduler.clear_context()
```

## 工作流程

### 1. 用户输入处理

```
用户输入 → 添加到上下文 → 意图识别 → 工具调度 → 结果返回
```

### 2. 意图识别

```python
# 使用IntentRecognizer
intent_result = {
    "intent": IntentType.GENERATE_VIDEO,
    "confidence": 0.92,
    "entities": {
        "description": "一只猫在草地上玩耍",
        "duration": 5,
        "aspect_ratio": "16:9"
    },
    "method": "llm"  # or "rule"
}
```

### 3. 工具调度

根据识别的意图调用对应方法：

- `GENERATE_VIDEO` → `_handle_generate_video()`
- `ANALYZE_VIDEO` → `_handle_analyze_video()`
- `CHAT/QUESTION` → `_handle_chat()`
- `HELP` → `_handle_help()`

### 4. 上下文管理

**添加消息**:
```python
context_manager.add_message(
    role="user",
    content="生成一个视频",
    metadata={"timestamp": 1234567890}
)
```

**自动压缩**:
当上下文长度超过阈值时，自动触发压缩：

```
检测长度 > 50000
   ↓
意图识别（如果已设置）
   ↓
按意图分类压缩
   ├─ 重要: 保留50%
   ├─ 普通: 提取关键词
   └─ 系统: 保留最近3条
   ↓
保存到长期记忆
   ↓
清空短期记忆
   ↓
添加压缩摘要
```

## 配置说明

### 调度器配置

```python
scheduler = AgentScheduler(
    session_id="user_123",              # 会话ID
    use_llm_intent=True,                # 使用LLM识别意图
    context_compression_threshold=50000  # 压缩阈值（字符数）
)
```

### 上下文管理器配置

```python
context_manager = ContextManager(
    max_context_length=100000,      # 最大上下文长度
    auto_compress_threshold=50000,  # 自动压缩阈值
    session_id="user_123",          # 会话ID
    llm_api_url="...",             # LLM API（用于压缩）
    llm_api_key="..."              # LLM API Key
)
```

## 扩展

### 添加新工具

1. 在 `_register_tools()` 中注册工具
2. 添加对应的 `_handle_xxx()` 方法
3. 更新意图类型（如需要）

```python
def _register_tools(self):
    # 新工具
    self.tools["new_tool"] = NewTool()

async def _handle_new_intent(self, user_input, entities, **kwargs):
    tool = self.tools["new_tool"]
    return await tool.execute(user_input)
```

### 自定义压缩策略

```python
# 设置自定义意图识别器
context_manager.set_intent_recognizer(custom_recognizer)

# 手动压缩
compression_result = await context_manager._intent_aware_compress()
```

## 最佳实践

1. **会话隔离**: 不同用户使用不同 `session_id`
2. **定期清理**: 长时间会话建议定期清空上下文
3. **监控压缩**: 关注压缩频率和压缩比
4. **意图优化**: 根据实际使用优化意图识别规则

## 性能考虑

- **上下文长度**: 建议阈值 30k-100k
- **压缩比**: 重要内容 0.5, 普通内容 0.2
- **向量存储**: 定期持久化到磁盘
- **意图识别**: LLM模式更准确但较慢，规则模式更快

## 故障排查

### Q: 上下文压缩过于频繁

A: 提高 `context_compression_threshold` 或优化消息内容

### Q: 意图识别不准确

A: 
- 检查 prompts/intent-recognition/index.yml
- 调整关键词规则
- 使用更强的LLM模型

### Q: 工具调用失败

A: 
- 检查配置文件 config/index.yml
- 确认API密钥有效
- 查看详细错误日志

