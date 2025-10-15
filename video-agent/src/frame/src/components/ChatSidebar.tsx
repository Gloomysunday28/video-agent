import type { Session } from '../types/chat'

interface ChatSidebarProps {
  sessionId: string
  sessions: Session[]
  isLoadingSessions: boolean
  onCreateNewSession: () => void
  onSwitchSession: (sessionId: string) => void
  onCopySessionLink: () => void
}

export function ChatSidebar({
  sessionId,
  sessions,
  isLoadingSessions,
  onCreateNewSession,
  onSwitchSession,
  onCopySessionLink
}: ChatSidebarProps) {
  return (
    <aside className="chat-sidebar">
      <div className="sidebar-header">
        <h2>🎬 Video Agent</h2>
        <p className="session-id">会话: {sessionId.slice(0, 8)}</p>
        <div className="session-actions">
          <button 
            className="new-chat-btn"
            onClick={onCreateNewSession}
            title="开始新对话"
          >
            ➕ 新建对话
          </button>
          <button 
            className="copy-session-btn"
            onClick={onCopySessionLink}
            title="复制会话链接"
          >
            📋 复制链接
          </button>
        </div>
      </div>
      
      <div className="sidebar-content">
        <div className="sidebar-section">
          <h3>📚 会话列表</h3>
          <div className="session-list">
            {isLoadingSessions ? (
              <div className="loading-sessions">
                <p>加载会话列表中...</p>
              </div>
            ) : (
              <>
                {sessions.map((session) => (
                  <div 
                    key={session.session_id} 
                    className={`session-item ${session.session_id === sessionId ? 'active' : ''}`}
                    onClick={() => onSwitchSession(session.session_id)}
                  >
                    <div className="session-title">
                      {session.title}
                    </div>
                    <div className="session-info">
                      <span className="session-count">{session.message_count} 条消息</span>
                      <span className="session-time">
                        {session.last_activity > 0 ? new Date(session.last_activity * 1000).toLocaleDateString() : '暂无活动'}
                      </span>
                    </div>
                  </div>
                ))}
                {sessions.length === 0 && (
                  <div className="session-empty">
                    <p>暂无会话</p>
                    <p className="session-hint">开始对话后会显示在这里</p>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <div className="sidebar-section">
          <h3>📝 快捷操作</h3>
          <div className="example-list">
            <div className="example-item" onClick={() => {
              const input = document.querySelector('.message-input') as HTMLTextAreaElement
              if (input) {
                input.value = '生成一个5秒的视频，内容是猫咪在草地上玩耍'
                input.dispatchEvent(new Event('input', { bubbles: true }))
              }
            }}>
              "生成一个5秒的视频，内容是猫咪在草地上玩耍"
            </div>
            <div className="example-item" onClick={() => {
              const input = document.querySelector('.message-input') as HTMLTextAreaElement
              if (input) {
                input.value = '分析这个视频的内容'
                input.dispatchEvent(new Event('input', { bubbles: true }))
              }
            }}>
              "分析这个视频的内容"
            </div>
            <div className="example-item" onClick={() => {
              const input = document.querySelector('.message-input') as HTMLTextAreaElement
              if (input) {
                input.value = '怎么使用这个助手？'
                input.dispatchEvent(new Event('input', { bubbles: true }))
              }
            }}>
              "怎么使用这个助手？"
            </div>
          </div>
        </div>
      </div>

      <div className="sidebar-footer">
        <a href="/" className="back-link">← 返回首页</a>
      </div>
    </aside>
  )
}
