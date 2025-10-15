import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import './ChatPage.css'

interface Message {
  role: 'user' | 'assistant' | 'error'
  content: string
  intent?: string
  timestamp?: number
}

function ChatPage() {
  const [searchParams] = useSearchParams()
  const [sessionId] = useState<string>(() => {
    // 从 URL 获取 session_id，如果没有则创建新的
    const idFromUrl = searchParams.get('id')
    return idFromUrl || crypto.randomUUID()
  })
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // 加载历史消息
  useEffect(() => {
    const loadHistory = async () => {
      const idFromUrl = searchParams.get('id')
      if (!idFromUrl) {
        // 新会话，不需要加载历史
        return
      }

      setIsLoadingHistory(true)
      try {
        const response = await fetch(`/api/chat/history/${idFromUrl}`)
        const data = await response.json()

        if (data.success && data.messages && data.messages.length > 0) {
          const historyMessages: Message[] = data.messages.map((msg: {
            role: string
            content: string
            timestamp: number
          }) => ({
            role: msg.role as 'user' | 'assistant' | 'error',
            content: msg.content,
            timestamp: msg.timestamp
          }))
          setMessages(historyMessages)
          console.log(`✓ 加载了 ${historyMessages.length} 条历史消息`)
        }
      } catch (error) {
        console.error('加载历史消息失败:', error)
      } finally {
        setIsLoadingHistory(false)
      }
    }

    loadHistory()
  }, [searchParams])

  // 自动聚焦输入框
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessage = inputValue.trim()
    setInputValue('')

    // 添加用户消息
    const newUserMessage: Message = {
      role: 'user',
      content: userMessage,
      timestamp: Date.now()
    }
    setMessages(prev => [...prev, newUserMessage])

    setIsLoading(true)

    try {
      const response = await fetch('/api/chat/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: userMessage,
        }),
      })

      const data = await response.json()

      // 提取回复内容
      let content = ''
      if (data.result?.result) {
        // 视频分析/生成等工具返回的详细结果
        content = data.result.result
      } else if (data.result?.description) {
        // 视频分析的描述字段
        content = data.result.description
      } else if (data.result?.message) {
        // 工具返回的消息
        content = data.result.message
      } else if (data.message) {
        // API 返回的消息
        content = data.message
      } else if (data.error) {
        // 错误信息
        content = `处理出错：${data.error}`
      } else {
        // 兜底
        content = JSON.stringify(data)
      }

      // 添加助手回复
      const assistantMessage: Message = {
        role: 'assistant',
        content: content,
        intent: data.intent,
        timestamp: Date.now()
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      const errorMessage: Message = {
        role: 'error',
        content: `发送失败: ${error}`,
        timestamp: Date.now()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-page">
      {/* 侧边栏 */}
      <aside className="chat-sidebar">
        <div className="sidebar-header">
          <h2>🎬 Video Agent</h2>
          <p className="session-id">会话: {sessionId.slice(0, 8)}</p>
          <div className="session-actions">
            <button 
              className="new-chat-btn"
              onClick={() => {
                window.location.href = '/chat'
              }}
              title="开始新对话"
            >
              ➕ 新建对话
            </button>
            <button 
              className="copy-session-btn"
              onClick={() => {
                const url = `${window.location.origin}/chat?id=${sessionId}`
                navigator.clipboard.writeText(url)
                alert('会话链接已复制！')
              }}
              title="复制会话链接"
            >
              📋 复制链接
            </button>
          </div>
        </div>
        
        <div className="sidebar-content">
          <div className="sidebar-section">
            <h3>💡 功能介绍</h3>
            <ul className="feature-list">
              <li>
                <span className="icon">🎥</span>
                <div>
                  <strong>视频生成</strong>
                  <p>通过文字描述生成AI视频</p>
                </div>
              </li>
              <li>
                <span className="icon">🔍</span>
                <div>
                  <strong>视频分析</strong>
                  <p>智能识别视频内容</p>
                </div>
              </li>
              <li>
                <span className="icon">💬</span>
                <div>
                  <strong>智能对话</strong>
                  <p>自然语言交互</p>
                </div>
              </li>
            </ul>
          </div>

          <div className="sidebar-section">
            <h3>📝 使用示例</h3>
            <div className="example-list">
              <div className="example-item" onClick={() => setInputValue('生成一个5秒的视频，内容是猫咪在草地上玩耍')}>
                "生成一个5秒的视频，内容是猫咪在草地上玩耍"
              </div>
              <div className="example-item" onClick={() => setInputValue('分析这个视频的内容')}>
                "分析这个视频的内容"
              </div>
              <div className="example-item" onClick={() => setInputValue('怎么使用这个助手？')}>
                "怎么使用这个助手？"
              </div>
            </div>
          </div>
        </div>

        <div className="sidebar-footer">
          <a href="/" className="back-link">← 返回首页</a>
        </div>
      </aside>

      {/* 主聊天区域 */}
      <main className="chat-main">
        <div className="chat-container">
          {/* 消息列表 */}
          <div className="messages-container">
            {isLoadingHistory ? (
              <div className="welcome-screen">
                <div className="welcome-icon">⏳</div>
                <h1>加载历史消息中...</h1>
                <p>正在恢复您的对话</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="welcome-screen">
                <div className="welcome-icon">🤖</div>
                <h1>你好！我是 Video Agent</h1>
                <p>我可以帮你生成视频、分析视频，或者回答你的问题</p>
                <div className="quick-actions">
                  <button onClick={() => setInputValue('生成一个视频')}>
                    ✨ 生成视频
                  </button>
                  <button onClick={() => setInputValue('分析视频')}>
                    🔍 分析视频
                  </button>
                  <button onClick={() => setInputValue('帮助')}>
                    ❓ 查看帮助
                  </button>
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg, index) => (
                  <div key={index} className={`message-wrapper ${msg.role}`}>
                    <div className="message-bubble">
                      <div className="message-header">
                        <span className="message-role">
                          {msg.role === 'user' ? '👤 你' : '🤖 助手'}
                        </span>
                        {msg.intent && (
                          <span className="message-intent">{msg.intent}</span>
                        )}
                      </div>
                      <div className="message-text">
                        {msg.role === 'assistant' ? (
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        ) : (
                          msg.content
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="message-wrapper assistant">
                    <div className="message-bubble">
                      <div className="message-header">
                        <span className="message-role">🤖 助手</span>
                      </div>
                      <div className="message-text">
                        <div className="typing-indicator">
                          <span></span>
                          <span></span>
                          <span></span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* 输入区域 */}
          <div className="input-container">
            <div className="input-wrapper">
              <textarea
                ref={inputRef}
                className="message-input"
                placeholder="问我任何问题..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
              />
              <div className="input-actions">
                <button
                  className="send-button"
                  onClick={handleSend}
                  disabled={!inputValue.trim() || isLoading}
                  title={isLoading ? '发送中...' : '发送'}
                />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default ChatPage

