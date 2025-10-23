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
  const activeEventSourceRef = useRef<EventSource | null>(null)

  // 当sessionId变化时，关闭现有的SSE连接
  useEffect(() => {
    return () => {
      closeActiveEventSource()
    }
  }, [sessionId])

  const closeActiveEventSource = () => {
    if (activeEventSourceRef.current) {
      try {
        activeEventSourceRef.current.close()
      } catch {
        // ignore
      }
      activeEventSourceRef.current = null
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
      addAssistantReply(message as unknown as { content: string; timestamp: string; task_id: string; message_type?: string })
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
        const params = new URLSearchParams()
        params.set('session_id', sessionId)
        params.set('message', userMessage)
        params.set('generator_type', generatorType) // 添加生成器类型参数
        if (videoFilename) params.set('video_filename', String(videoFilename))
        if (imageFile) params.set('image_file', imageFile)
        if (imageFilename) params.set('image_filename', String(imageFilename))

        // 确保同一时间只有一条 SSE 连接
        closeActiveEventSource()
        const es = new EventSource(`/api/chat/stream?${params.toString()}`)
        activeEventSourceRef.current = es

        es.onopen = () => {
          console.log('[SSE] connection opened')
        }

        es.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data)
            handleWebSocketMessage(msg as unknown as { type: string; [key: string]: unknown })
            // 仅在收到最终助手回复或失败状态时关闭
            if (msg.type === 'assistant_reply' || (msg.type === 'task_status' && msg.status === 'failed')) {
              es.close()
              setIsLoading(false)
            }
          } catch (e) {
            console.error('解析SSE消息失败:', e)
          }
        }

        es.onerror = (e) => {
          console.error('SSE 错误:', e)
          closeActiveEventSource()
          setIsLoading(false)
        }
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
        const params = new URLSearchParams()
        params.set('session_id', sessionId)
        params.set('message', lastUserMessage)
        params.set('generator_type', generatorType) // 添加生成器类型参数
        if (lastVideoFilename) params.set('video_filename', String(lastVideoFilename))

        closeActiveEventSource()
        const es = new EventSource(`/api/chat/stream?${params.toString()}`)
        activeEventSourceRef.current = es

        es.onopen = () => {
          console.log('[SSE][retry] connection opened')
        }

        es.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data)
            console.log('[SSE][retry] message:', msg)
            handleWebSocketMessage(msg as unknown as { type: string; [key: string]: unknown })
            if (msg.type === 'assistant_reply' || (msg.type === 'task_status' && msg.status === 'failed')) {
              closeActiveEventSource()
              setIsLoading(false)
            }
          } catch (e) {
            console.error('解析SSE消息失败:', e)
          }
        }

        es.onerror = (e) => {
          console.error('SSE 错误:', e)
          es.close()
          setIsLoading(false)
        }
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
