import { useSession } from '../hooks/useSession'
import { useSessions } from '../hooks/useSessions'
import { useChat } from '../hooks/useChat'
import { useSSE } from '../hooks/useSSE'
import { ChatSidebar } from '../components/ChatSidebar'
import { ChatMessages } from '../components/ChatMessages'
import { ChatInput } from '../components/ChatInput'
import { TaskStatusList } from '../components/TaskStatus'
import type { TaskStatus } from '../hooks/useSSE'
import { useState, useEffect } from 'react'
import './ChatPage.css'

function ChatPage() {
  const { sessionId, createNewSession, switchToSession } = useSession()
  const { sessions, isLoadingSessions } = useSessions()
  const { 
    inputValue, 
    setInputValue, 
    messages, 
    isLoading, 
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
  } = useChat(sessionId)
  
  // 事件流连接和状态管理（仅作状态条用途，避免和对话流重复）
  const { messages: allMessages } = useSSE(sessionId, false)
  const [taskStatuses, setTaskStatuses] = useState<TaskStatus[]>([])

  // 处理WebSocket消息
  useEffect(() => {
    if (allMessages && allMessages.length > 0) {
      
      // 处理所有消息，按task_id分组
      const messageMap = new Map<string, TaskStatus>()
      
      // 处理新消息，避免重复
      const processedMessages = new Set<string>()
      
      allMessages.forEach(message => {
        // 为每个消息创建唯一标识
        const messageKey = `${message.type}_${message.task_id}_${message.timestamp}`
        
        if (!processedMessages.has(messageKey)) {
          processedMessages.add(messageKey)
          
          // 处理WebSocket消息
          handleWebSocketMessage(message as unknown as { type: string; [key: string]: unknown })
          
          if (message.task_id && (message.type === 'task_status' || message.type === 'task_progress')) {
            // 对于相同task_id的状态消息，保留最新的
            if (!messageMap.has(message.task_id) || 
                new Date(message.timestamp as unknown as string) > new Date(messageMap.get(message.task_id)!.timestamp)) {
              messageMap.set(message.task_id as string, message as unknown as TaskStatus)
            }
          }
        }
      })
      
      // 更新任务状态
      setTaskStatuses(Array.from(messageMap.values()))
    }
  }, [allMessages, handleWebSocketMessage])
  // 清理已完成或失败的任务状态（5秒后）
  useEffect(() => {
    const timer = setTimeout(() => {
      setTaskStatuses(prev => 
        prev.filter(status => 
          !status.task_id || 
          (status.status !== 'completed' && status.status !== 'failed')
        )
      )
    }, 5000)

    return () => clearTimeout(timer)
  }, [taskStatuses])

  const handleDismissStatus = (taskId: string) => {
    setTaskStatuses(prev => prev.filter(status => status.task_id !== taskId))
  }

  const handleCreateNewSession = () => {
    createNewSession()
    clearMessages()
    setTaskStatuses([]) // 清空任务状态
  }

  const handleSwitchSession = (targetSessionId: string) => {
    // 切换会话，让 useMessages hook 自动处理历史消息加载
    switchToSession(targetSessionId)
    // 不要手动清空消息，让 useMessages hook 处理
    setTaskStatuses([]) // 只清空任务状态
  }

  const handleCopySessionLink = () => {
    const url = `${window.location.origin}/chat?id=${sessionId}`
    navigator.clipboard.writeText(url)
    alert('会话链接已复制！')
  }

  return (
    <div className="chat-page">
      {/* 侧边栏 */}
      <ChatSidebar
        sessionId={sessionId}
        sessions={sessions}
        isLoadingSessions={isLoadingSessions}
        onCreateNewSession={handleCreateNewSession}
        onSwitchSession={handleSwitchSession}
        onCopySessionLink={handleCopySessionLink}
      />

      {/* 主聊天区域 */}
      <main className="chat-main">
        {/* 任务状态列表 - 只显示进行中的任务 */}
        {taskStatuses.filter(status => 
          status.status === 'pending' || 
          status.status === 'processing'
        ).length > 0 && (
          <div className="task-status-container">
            <TaskStatusList 
              statuses={taskStatuses.filter(status => 
                status.status === 'pending' || 
                status.status === 'processing'
              )}
              onDismissStatus={handleDismissStatus}
            />
          </div>
        )}

        {/* 消息区域 */}
        <ChatMessages 
          messages={messages} 
          isLoading={isLoading} 
          onRetry={handleRetry}
        />

        {/* 已上传的文件信息 */}
        {videoFile && (
          <div className="uploaded-file-info">
            <div className="file-info">
              <span className="file-icon">🎥</span>
              <span className="file-name">{videoFilename}</span>
              <button className="clear-file-btn" onClick={clearVideo}>✕</button>
            </div>
          </div>
        )}
        {imageFile && (
          <div className="uploaded-file-info">
            <div className="file-info">
              <span className="file-icon">🖼️</span>
              <span className="file-name">{imageFilename}</span>
              <button className="clear-file-btn" onClick={clearImage}>✕</button>
            </div>
          </div>
        )}

        {/* 输入区域 */}
        <ChatInput
          inputValue={inputValue}
          setInputValue={setInputValue}
          onSend={handleSend}
          isLoading={isLoading}
          onVideoSelect={handleVideoSelect}
          onImageSelect={handleImageSelect}
          generatorType={generatorType}
          setGeneratorType={setGeneratorType}
        />
      </main>
    </div>
  )
}

export default ChatPage