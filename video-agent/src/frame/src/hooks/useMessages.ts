import { useState, useEffect } from 'react'
import type { Message, ChatResponse } from '../types/chat'

export function useMessages(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)

  // 加载历史消息
  useEffect(() => {
    const loadHistory = async () => {
      if (!sessionId) return

      setIsLoadingHistory(true)
      try {
        const response = await fetch(`/api/chat/history/${sessionId}`)
        const data = await response.json()

        if (data.success && data.messages && data.messages.length > 0) {
          const historyMessages: Message[] = data.messages.map((msg: {
            role: string
            content: string
            timestamp: number
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
              timestamp: msg.timestamp,
              metadata: msg.metadata
            }
          })
          setMessages(historyMessages)
          console.log(`✓ 加载了 ${historyMessages.length} 条历史消息`)
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
    type MaybeNested = ChatResponse & { result?: { success?: boolean; error?: string; [k: string]: unknown } }
    const nested = (response as MaybeNested).result
    const nestedSuccess = nested?.success
    const nestedError = nested?.error as string | undefined

    if (nestedSuccess === false && nestedError) {
      content = `处理出错：${nestedError}`
    } else if (response.success === false && response.error) {
      // 处理扁平结构的失败响应 { success: false, error: '...' }
      content = `处理出错：${response.error}`
    } else if (response.result?.result) {
      content = response.result.result
    } else if (response.result?.description) {
      content = response.result.description
    } else if (response.result?.message) {
      content = response.result.message
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

  const clearMessages = () => {
    setMessages([])
  }

  return {
    messages,
    isLoadingHistory,
    addUserMessage,
    addAssistantMessage,
    addErrorMessage,
    clearMessages
  }
}
