import { useSession } from '../hooks/useSession'
import { useSessions } from '../hooks/useSessions'
import { useChat } from '../hooks/useChat'
import { ChatSidebar } from '../components/ChatSidebar'
import { ChatMessages } from '../components/ChatMessages'
import { ChatInput } from '../components/ChatInput'
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
    clearVideo
  } = useChat(sessionId)

  const handleCreateNewSession = () => {
    createNewSession()
    clearMessages()
  }

  const handleSwitchSession = (targetSessionId: string) => {
    switchToSession(targetSessionId)
    clearMessages() // 清空当前消息，历史消息会在useEffect中加载
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
        {/* 消息区域 */}
        <ChatMessages 
          messages={messages} 
          isLoading={isLoading} 
          onRetry={handleRetry}
        />

        {/* 已上传的视频信息 */}
        {videoFile && (
          <div className="uploaded-video-info">
            <div className="video-info">
              <span className="video-icon">🎥</span>
              <span className="video-name">{videoFilename}</span>
              <button className="clear-video-btn" onClick={clearVideo}>✕</button>
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
        />
      </main>
    </div>
  )
}

export default ChatPage