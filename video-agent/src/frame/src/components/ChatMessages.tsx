import ReactMarkdown from 'react-markdown'
import type { Message } from '../types/chat'

interface ChatMessagesProps {
  messages: Message[]
  isLoadingHistory?: boolean
  isLoading?: boolean
  onRetry?: () => void
}

export function ChatMessages({ messages, isLoadingHistory = false, isLoading = false, onRetry }: ChatMessagesProps) {

  if (isLoadingHistory) {
    return (
      <div className="messages-container">
        <div className="loading-messages">
          <p>加载历史消息中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="messages-container">
      {messages.length === 0 ? (
        <div className="welcome-message">
          <div className="welcome-layout">
            <div className="welcome-left">
              <div className="welcome-icon">🎬</div>
              <h1>Video Agent</h1>
              <p className="welcome-subtitle">AI视频创作与分析助手</p>
              <p className="welcome-description">
                专业的AI视频工具，为您提供智能视频生成、内容分析和专业对话服务。
                无论是创意视频制作还是内容理解，我们都能为您提供强大的AI支持。
              </p>
              <p className="welcome-hint">在下方输入框开始对话</p>
            </div>
            <div className="welcome-right">
              <div className="tools-section">
                <h3>核心功能</h3>
                <div className="tool-item">
                  <div className="tool-icon">🎥</div>
                  <div className="tool-content">
                    <h4>视频生成</h4>
                    <p>AI创作高质量视频内容</p>
                  </div>
                </div>
                <div className="tool-item">
                  <div className="tool-icon">🔍</div>
                  <div className="tool-content">
                    <h4>视频分析</h4>
                    <p>智能解析视频内容</p>
                  </div>
                </div>
                <div className="tool-item">
                  <div className="tool-icon">💬</div>
                  <div className="tool-content">
                    <h4>智能对话</h4>
                    <p>专业的视频领域问答</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        messages.map((message, index) => (
          <div key={index} className={`message-wrapper ${message.role}`}>
            <div className="message-bubble">
              <div className="message-header">
                <span className="message-role">
                  {message.role === 'user' ? '👤 你' : 
                   message.role === 'system' ? '🔧 系统' : '🤖 助手'}
                </span>
                {message.intent && (
                  <span className="message-intent">{message.intent}</span>
                )}
              </div>
              <div className="message-text">
                {message.role === 'assistant' ? (
                  (message.content?.startsWith('处理出错：') || 
                   (message.content.includes('{') && message.content.includes('success') && message.content.includes('False'))) ? (
                    <div className="error-message">
                      <span>
                        {message.content?.startsWith('处理出错：') ? 
                          message.content : 
                          '处理出错：服务器连接异常，请重试'
                        }
                      </span>
                      {onRetry && (
                        <div className="retry-row">
                          <button className="retry-button" onClick={onRetry} title="重试">
                            🔄 重试
                          </button>
                        </div>
                      )}
                    </div>
                  ) : message.metadata?.isStatusUpdate ? (
                    <div className="status-message">
                      <span>{message.content}</span>
                      {message.metadata?.progress !== undefined && (
                        <div className="progress-bar">
                          <div 
                            className="progress-fill" 
                            style={{ width: `${message.metadata.progress}%` }}
                          ></div>
                        </div>
                      )}
                    </div>
                  ) : message.metadata?.isFinalReply || message.contentType === 'video' || message.contentType === 'image' ? (
                    <div>
                      {message.contentType === 'video' ? (
                        <div className="video-result">
                          {(() => {
                            const videoUrl = message.content;
                            
                            // 检查是否是本地生成的视频文件路径
                            if (videoUrl.includes('generated_videos/')) {
                              const videoMatch = videoUrl.match(/generated_videos\/([^\\s]+\.mp4)/);
                              if (videoMatch) {
                                const videoFilename = videoMatch[1];
                                const localVideoUrl = `/api/generated_videos/${videoFilename}`;
                                return (
                                  <video controls width="100%" style={{ maxWidth: '500px', marginTop: '10px' }}>
                                    <source src={localVideoUrl} type="video/mp4" />
                                    您的浏览器不支持视频播放。
                                  </video>
                                );
                              }
                            }
                            
                            // 对于HTTP/HTTPS URL，直接显示
                            if (videoUrl.startsWith('http')) {
                              return (
                                <video controls width="100%" style={{ maxWidth: '500px', marginTop: '10px' }}>
                                  <source src={videoUrl} type="video/mp4" />
                                  您的浏览器不支持视频播放。
                                </video>
                              );
                            }
                            
                            return <p>视频URL: {videoUrl}</p>;
                          })()}
                        </div>
                      ) : message.contentType === 'image' ? (
                        <div className="image-result">
                          {(() => {
                            const imageUrl = message.content;
                            
                            // 对于HTTP/HTTPS URL，直接显示图片
                            if (imageUrl.startsWith('http')) {
                              return (
                                <img 
                                  src={imageUrl} 
                                  alt="生成的图片" 
                                  style={{ 
                                    width: '100%', 
                                    maxWidth: '500px', 
                                    marginTop: '10px',
                                    borderRadius: '8px',
                                    boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
                                  }} 
                                />
                              );
                            }
                            
                            return <p>图片URL: {imageUrl}</p>;
                          })()}
                        </div>
                      ) : (
                        <ReactMarkdown>{message.content}</ReactMarkdown>
                      )}
                    </div>
                  ) : (
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  )
                ) : message.role === 'error' ? (
                  <div className="error-message">
                    <span>{message.content}</span>
                    {onRetry && (
                      <div className="retry-row">
                        <button className="retry-button" onClick={onRetry} title="重试">
                          🔄 重试
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  message.content
                )}
              </div>
            </div>
          </div>
               ))
             )}
             
             {/* Loading 状态 */}
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
             
             <div ref={(el) => {
               if (el) {
                 el.scrollIntoView({ behavior: 'smooth' })
               }
             }} />
           </div>
         )
       }
