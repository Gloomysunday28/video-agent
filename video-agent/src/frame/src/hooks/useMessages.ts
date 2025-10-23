import { useState, useEffect } from 'react'
import type { Message, ChatResponse } from '../types/chat'
// 仅类型定义，避免依赖解析问题
type TaskStatus = {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  message: string
  progress?: number
  timestamp?: string
  type?: string
}

export function useMessages(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)

  // 加载历史消息
  useEffect(() => {
    const loadHistory = async () => {
      if (!sessionId) return

      // 清空当前消息，准备加载新会话的历史消息
      setMessages([])
      setIsLoadingHistory(true)
      
      try {
        const response = await fetch(`/api/chat/history/${sessionId}`)
        const data = await response.json()

        if (data.success && data.messages && data.messages.length > 0) {
          const historyMessages: Message[] = data.messages.map((msg: {
            role: string
            content: string
            timestamp: number
            message_type?: string
            metadata?: {
              title?: string
              [key: string]: unknown
            }
          }) => {
            // 解析可能包含JSON的错误消息
            let content = msg.content
            if (msg.role === 'assistant' && content.includes('{') && content.includes('success')) {
              try {
                // 尝试解析JSON格式的错误消息
                const parsed = JSON.parse(content.replace(/'/g, '"'))
                if (parsed.success === false && parsed.error) {
                  content = `处理出错：${parsed.error}`
                }
              } catch (e) {
                // 如果解析失败，保持原内容
                console.log('解析失败:', e)
              }
            }
            
            return {
              role: msg.role as 'user' | 'assistant' | 'error',
              content,
              contentType: (msg.message_type as 'text' | 'video' | 'image' | 'file') || 'text',  // 映射message_type到contentType
              timestamp: msg.timestamp,
              metadata: msg.metadata
            }
          })
          setMessages(historyMessages)
        } else {
          setMessages([])
        }
      } catch (error) {
        console.error('加载历史消息失败:', error)
        setMessages([])
      } finally {
        setIsLoadingHistory(false)
      }
    }

    loadHistory()
  }, [sessionId])

  const addUserMessage = (content: string) => {
    const userMessage: Message = {
      role: 'user',
      content,
      timestamp: Math.floor(Date.now() / 1000) // 转换为秒级时间戳
    }
    setMessages(prev => [...prev, userMessage])
  }

  const addAssistantMessage = (response: ChatResponse) => {
    let content = ''

    // 优先处理嵌套的失败响应 { result: { success: false, error: ... } }
    type MaybeNested = ChatResponse & { result?: { success?: boolean; error?: string; result?: string; description?: string; message?: string; [k: string]: unknown } }
    const nested = (response as MaybeNested).result
    const nestedSuccess = nested?.success
    const nestedError = nested?.error as string | undefined

    if (nestedSuccess === false && nestedError) {
      content = `处理出错：${nestedError}`
    } else if (response.success === false && response.error) {
      // 处理扁平结构的失败响应 { success: false, error: '...' }
      content = `处理出错：${response.error}`
    } else if (nested?.result) {
      content = nested.result
    } else if (nested?.description) {
      content = nested.description
    } else if (nested?.message) {
      content = nested.message
    } else if (response.message) {
      content = response.message
    } else if (response.error) {
      content = `处理出错：${response.error}`
    } else {
      // 如果是失败响应，显示更友好的错误信息
      if (response.success === false) {
        content = '抱歉，处理请求时出现了问题，请稍后重试。'
      } else {
        content = JSON.stringify(response)
      }
    }

    const assistantMessage: Message = {
      role: 'assistant',
      content,
      intent: response.intent,
      timestamp: Math.floor(Date.now() / 1000) // 转换为秒级时间戳
    }
    setMessages(prev => [...prev, assistantMessage])
  }

  const addErrorMessage = (error: string) => {
    const errorMessage: Message = {
      role: 'error',
      content: `发送失败: ${error}`,
      timestamp: Math.floor(Date.now() / 1000) // 转换为秒级时间戳
    }
    setMessages(prev => [...prev, errorMessage])
  }

  const addAssistantReply = (messageData: { content: string; timestamp: string; task_id: string; message_type?: string }) => {
    console.log('[useMessages] addAssistantReply 接收到的数据:', messageData)
    
    const assistantMessage: Message = {
      role: 'assistant',
      content: messageData.content,
      contentType: (messageData.message_type as 'text' | 'video' | 'image' | 'file') || 'text',
      timestamp: Math.floor(new Date(messageData.timestamp).getTime() / 1000),
      metadata: {
        task_id: messageData.task_id,
        isFinalReply: true // 标记这是最终回复
      }
    }

    console.log('[useMessages] 创建的消息对象:', assistantMessage)
    setMessages(prev => [...prev, assistantMessage])
  }

  const addSystemMessage = (taskStatus: TaskStatus) => {
    // 格式化助手消息内容
    let content = ''
    let icon = ''
    
    switch (taskStatus.status) {
      case 'pending':
        icon = '⏳'
        content = `${icon} ${taskStatus.message}`
        break
      case 'processing':
        icon = '🔄'
        if (taskStatus.progress !== undefined) {
          content = `${icon} ${taskStatus.message} (${Math.round(taskStatus.progress)}%)`
        } else {
          content = `${icon} ${taskStatus.message}`
        }
        break
      case 'completed':
        icon = '✅'
        content = `${icon} ${taskStatus.message}`
        // 完成状态时，如果没有进度信息，设置为100%
        if (taskStatus.progress === undefined) {
          taskStatus.progress = 100
        }
        break
      case 'failed':
        icon = '❌'
        content = `${icon} ${taskStatus.message}`
        // 失败状态时，如果没有进度信息，设置为0%
        if (taskStatus.progress === undefined) {
          taskStatus.progress = 0
        }
        break
      default:
        icon = 'ℹ️'
        content = `${icon} ${taskStatus.message}`
    }

    const assistantMessage: Message = {
      role: 'assistant',
      content,
      timestamp: Math.floor(new Date(taskStatus.timestamp || Date.now()).getTime() / 1000),
      metadata: {
        task_id: taskStatus.task_id,
        status: taskStatus.status,
        progress: taskStatus.progress,
        isStatusUpdate: true // 标记这是状态更新消息
      }
    }

    setMessages(prev => {
      // 检查是否已存在相同task_id的助手消息，如果存在则更新，否则添加新消息
      const existingIndex = prev.findIndex(msg => 
        msg.metadata?.task_id === taskStatus.task_id && 
        msg.role === 'assistant' && 
        msg.metadata?.isStatusUpdate === true
      )
      
      if (existingIndex >= 0) {
        // 更新现有消息
        const newMessages = [...prev]
        newMessages[existingIndex] = assistantMessage
        
        // 如果任务完成或失败，保持消息显示，但不再更新
        return newMessages
      } else {
        // 添加新消息
        return [...prev, assistantMessage]
      }
    })
  }

  const clearMessages = () => {
    setMessages([])
  }

  return {
    messages,
    isLoadingHistory,
    addUserMessage,
    addAssistantMessage,
    addErrorMessage,
    addSystemMessage,
    addAssistantReply,
    clearMessages
  }
}
