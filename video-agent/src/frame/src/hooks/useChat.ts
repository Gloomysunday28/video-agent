import { useState } from 'react'
import type { ChatResponse } from '../types/chat'
import { useMessages } from './useMessages'
import { useSessions } from './useSessions'

export function useChat(sessionId: string) {
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [videoFile, setVideoFile] = useState<string | null>(null)
  const [videoFilename, setVideoFilename] = useState<string | null>(null)
  const [lastUserMessage, setLastUserMessage] = useState<string | null>(null)
  const [lastVideoFile, setLastVideoFile] = useState<string | null>(null)
  const [lastVideoFilename, setLastVideoFilename] = useState<string | null>(null)
  
  const { messages, isLoadingHistory, addUserMessage, addAssistantMessage, addErrorMessage, clearMessages } = useMessages(sessionId)
  const { refreshSessions } = useSessions()

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessage = inputValue.trim()
    setInputValue('')

    // 保存最后一条用户消息（用于重试）
    setLastUserMessage(userMessage)
    setLastVideoFile(videoFile)
    setLastVideoFilename(videoFilename)
    
    // 添加用户消息
    addUserMessage(userMessage)
    setIsLoading(true)

    try {
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
        }),
      })

      const data: ChatResponse = await response.json()
      
      if (data.success) {
        addAssistantMessage(data)
      } else {
        addErrorMessage(data.error || '未知错误')
      }
      
      // 刷新会话列表
      await refreshSessions()
    } catch (error) {
      addErrorMessage(error instanceof Error ? error.message : String(error))
    } finally {
      setIsLoading(false)
    }
  }

  const handleVideoSelect = (file: File, base64: string) => {
    setVideoFile(base64)
    setVideoFilename(file.name)
    // 自动添加分析视频的消息
    if (!inputValue.trim()) {
      setInputValue('分析这个视频的内容')
    }
  }

  const clearVideo = () => {
    setVideoFile(null)
    setVideoFilename(null)
  }

  const handleRetry = async () => {
    if (!lastUserMessage || isLoading) return

    setIsLoading(true)
    
    try {
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
        }),
      })

      const data: ChatResponse = await response.json()
      
      if (data.success) {
        addAssistantMessage(data)
      } else {
        addErrorMessage(data.error || '未知错误')
      }
      
      // 刷新会话列表
      await refreshSessions()
    } catch (error) {
      addErrorMessage(error instanceof Error ? error.message : String(error))
    } finally {
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
    clearVideo
  }
}
