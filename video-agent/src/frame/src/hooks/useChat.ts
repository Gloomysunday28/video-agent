import { useState, useRef, useEffect } from 'react'
import type { ChatResponse } from '../types/chat'
import { useMessages } from './useMessages'
import { useSessions } from './useSessions'
// 仅类型定义，避免依赖解析问题
type TaskStatus = {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  message: string
  progress?: number
  timestamp?: string
  type?: string
}

export function useChat(sessionId: string) {
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [videoFile, setVideoFile] = useState<string | null>(null)
  const [videoFilename, setVideoFilename] = useState<string | null>(null)
  const [imageFile, setImageFile] = useState<string | null>(null)
  const [imageFilename, setImageFilename] = useState<string | null>(null)
  const [lastUserMessage, setLastUserMessage] = useState<string | null>(null)
  const [lastVideoFile, setLastVideoFile] = useState<string | null>(null)
  const [lastVideoFilename, setLastVideoFilename] = useState<string | null>(null)
  const [lastImageFile, setLastImageFile] = useState<string | null>(null)
  const [lastImageFilename, setLastImageFilename] = useState<string | null>(null)
  const [generatorType, setGeneratorType] = useState<string>('doubao') // 默认使用doubao（实际调用bantouyan）
  
  const { messages, isLoadingHistory, addUserMessage, addAssistantMessage, addErrorMessage, addSystemMessage, addAssistantReply, clearMessages } = useMessages(sessionId)
  const { refreshSessions } = useSessions()
  const abortControllerRef = useRef<AbortController | null>(null)

  // 当sessionId变化时，取消现有的流式连接
  useEffect(() => {
    return () => {
      cancelActiveStream()
    }
  }, [sessionId])

  const cancelActiveStream = () => {
    if (abortControllerRef.current) {
      try {
        abortControllerRef.current.abort()
      } catch {
        // ignore
      }
      abortControllerRef.current = null
    }
  }

  // 处理WebSocket状态消息的函数
  const handleWebSocketMessage = (message: { type: string; [key: string]: unknown }) => {
    // 调试：统一打印收到的消息（精简字段）
    try {
      const m = message as { type?: string; status?: string; progress?: number; task_id?: string }
      console.log('[SSE][handleWebSocketMessage] message:', {
        type: m.type,
        status: m.status,
        progress: m.progress,
        task_id: m.task_id,
      })
    } catch {
      // ignore
    }
    if (message.type === 'task_status' || message.type === 'task_progress') {
      // 只处理真正的状态消息，确保有status字段
      if (message.status && (message.status === 'pending' || message.status === 'processing' || message.status === 'completed' || message.status === 'failed')) {
        // 检查是否为需要显示进度的任务类型
        const taskMessage = (message as { message?: string }).message || ''
        const isProgressTask = taskMessage.includes('生成') || taskMessage.includes('分析') || taskMessage.includes('处理视频') || taskMessage.includes('处理图片')
        
        // 只有进度任务才显示状态消息，普通聊天不显示
        if (isProgressTask) {
          addSystemMessage(message as unknown as TaskStatus)
        }
      }
    } else if (message.type === 'assistant_reply') {
      // 处理助手回复消息
      console.log('[useChat] 接收到assistant_reply:', message)
      const reply = message as unknown as { content: string; timestamp: string; task_id: string; message_type?: string }
      addAssistantReply(reply)
    }
  }

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessage = inputValue.trim()
    setInputValue('')

    // 保存最后一条用户消息（用于重试）
    setLastUserMessage(userMessage)
    setLastVideoFile(videoFile)
    setLastVideoFilename(videoFilename)
    setLastImageFile(imageFile)
    setLastImageFilename(imageFilename)
    
    // 添加用户消息
    addUserMessage(userMessage)
    setIsLoading(true)

    try {
      // 如果没有上传视频，优先使用新的 SSE 流式接口（图片文件也走SSE）
      if (!videoFile) {
        const requestBody = {
          session_id: sessionId,
          message: userMessage,
          generator_type: generatorType,
          video_filename: videoFilename || undefined,
          image_file: imageFile || undefined,
          image_filename: imageFilename || undefined,
        }

        // 确保同一时间只有一条连接
        cancelActiveStream()
        
        // 创建新的 AbortController
        const abortController = new AbortController()
        abortControllerRef.current = abortController
        
        const response = await fetch('/api/chat/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestBody),
          signal: abortController.signal,
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()

        if (!reader) {
          throw new Error('无法获取响应流')
        }

        console.log('[SSE] connection opened (fetch stream)')

        const processStream = async () => {
          try {
            let buffer = ''
            
            while (true) {
              const { done, value } = await reader.read()
              
              if (done) {
                console.log('[SSE] stream closed')
                setIsLoading(false)
                break
              }

              buffer += decoder.decode(value, { stream: true })
              const lines = buffer.split('\n')
              buffer = lines.pop() || ''

              for (const line of lines) {
                if (line.startsWith('data: ')) {
                  try {
                    const msg = JSON.parse(line.slice(6))
                    handleWebSocketMessage(msg as unknown as { type: string; [key: string]: unknown })
                    
                    // 仅在收到最终助手回复或失败状态时关闭
                    if (msg.type === 'assistant_reply' || (msg.type === 'task_status' && msg.status === 'failed')) {
                      reader.cancel()
                      setIsLoading(false)
                      return
                    }
                  } catch (e) {
                    console.error('解析SSE消息失败:', e)
                  }
                }
              }
            }
          } catch (e) {
            // 忽略 AbortError（用户主动取消）
            if (e instanceof Error && e.name === 'AbortError') {
              console.log('[SSE] stream aborted by user')
            } else {
              console.error('SSE 错误:', e)
              addErrorMessage(e instanceof Error ? e.message : String(e))
            }
            setIsLoading(false)
          }
        }

        processStream()
      } else {
        const response = await fetch('/api/chat/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message: userMessage,
            session_id: sessionId,
            video_file: videoFile,
            video_filename: videoFilename,
            image_file: imageFile,
            image_filename: imageFilename,
            generator_type: generatorType,
          }),
        })

        const data: ChatResponse = await response.json()
        
        if (data.success) {
          addAssistantMessage(data)
        } else {
          addErrorMessage(data.error || '未知错误')
        }
        
        await refreshSessions()
        setIsLoading(false)
      }
    } catch (error) {
      addErrorMessage(error instanceof Error ? error.message : String(error))
      setIsLoading(false)
    }
  }

  const handleVideoSelect = (file: File, base64: string) => {
    setVideoFile(base64)
    setVideoFilename(file.name)
  }

  const handleImageSelect = (file: File, base64: string) => {
    setImageFile(base64)
    setImageFilename(file.name)
  }

  const clearVideo = () => {
    setVideoFile(null)
    setVideoFilename(null)
  }

  const clearImage = () => {
    setImageFile(null)
    setImageFilename(null)
  }

  const handleRetry = async () => {
    if (!lastUserMessage || isLoading) return

    setIsLoading(true)
    
    try {
      if (!lastVideoFile && !lastImageFile) {
        const requestBody = {
          session_id: sessionId,
          message: lastUserMessage,
          generator_type: generatorType,
          video_filename: lastVideoFilename || undefined,
        }

        cancelActiveStream()
        
        // 创建新的 AbortController
        const abortController = new AbortController()
        abortControllerRef.current = abortController
        
        const response = await fetch('/api/chat/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestBody),
          signal: abortController.signal,
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()

        if (!reader) {
          throw new Error('无法获取响应流')
        }

        console.log('[SSE][retry] connection opened (fetch stream)')

        const processStream = async () => {
          try {
            let buffer = ''
            
            while (true) {
              const { done, value } = await reader.read()
              
              if (done) {
                console.log('[SSE][retry] stream closed')
                setIsLoading(false)
                break
              }

              buffer += decoder.decode(value, { stream: true })
              const lines = buffer.split('\n')
              buffer = lines.pop() || ''

              for (const line of lines) {
                if (line.startsWith('data: ')) {
                  try {
                    const msg = JSON.parse(line.slice(6))
                    console.log('[SSE][retry] message:', msg)
                    handleWebSocketMessage(msg as unknown as { type: string; [key: string]: unknown })
                    
                    if (msg.type === 'assistant_reply' || (msg.type === 'task_status' && msg.status === 'failed')) {
                      reader.cancel()
                      setIsLoading(false)
                      return
                    }
                  } catch (e) {
                    console.error('解析SSE消息失败:', e)
                  }
                }
              }
            }
          } catch (e) {
            // 忽略 AbortError（用户主动取消）
            if (e instanceof Error && e.name === 'AbortError') {
              console.log('[SSE][retry] stream aborted by user')
            } else {
              console.error('SSE 错误:', e)
              addErrorMessage(e instanceof Error ? e.message : String(e))
            }
            setIsLoading(false)
          }
        }

        processStream()
      } else {
        const response = await fetch('/api/chat/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message: lastUserMessage,
            session_id: sessionId,
            video_file: lastVideoFile,
            video_filename: lastVideoFilename,
            image_file: lastImageFile,
            image_filename: lastImageFilename,
            generator_type: generatorType,
          }),
        })

        const data: ChatResponse = await response.json()
        
        if (data.success) {
          addAssistantMessage(data)
        } else {
          addErrorMessage(data.error || '未知错误')
        }
        
        await refreshSessions()
        setIsLoading(false)
      }
    } catch (error) {
      addErrorMessage(error instanceof Error ? error.message : String(error))
      setIsLoading(false)
    }
  }

  return {
    inputValue,
    setInputValue,
    messages,
    isLoading,
    isLoadingHistory,
    handleSend,
    handleRetry,
    clearMessages,
    videoFile,
    videoFilename,
    handleVideoSelect,
    clearVideo,
    imageFile,
    imageFilename,
    handleImageSelect,
    clearImage,
    handleWebSocketMessage,
    generatorType,
    setGeneratorType
  }
}
