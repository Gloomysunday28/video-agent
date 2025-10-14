import { useState, useEffect } from 'react'
import './App.css'

interface Video {
  id: number
  title: string
  duration: string
}

interface ApiResponse {
  videos?: Video[]
  status?: string
  message?: string
}

function App() {
  const [videos, setVideos] = useState<Video[]>([])
  const [health, setHealth] = useState<string>('')
  const [loading, setLoading] = useState(false)

  // 检查后端健康状态
  const checkHealth = async () => {
    try {
      const response = await fetch('/api/health')
      const data: ApiResponse = await response.json()
      setHealth(data.message || 'OK')
    } catch (error) {
      setHealth('后端连接失败')
      console.error('Health check failed:', error)
    }
  }

  // 获取视频列表
  const fetchVideos = async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/videos')
      const data: ApiResponse = await response.json()
      setVideos(data.videos || [])
    } catch (error) {
      console.error('Failed to fetch videos:', error)
    } finally {
      setLoading(false)
    }
  }

  // 处理视频
  const processVideo = async (videoId: number) => {
    try {
      const response = await fetch(`/api/videos/process?video_id=${videoId}`, {
        method: 'POST',
      })
      const data: ApiResponse = await response.json()
      alert(data.message || '处理成功')
    } catch (error) {
      console.error('Failed to process video:', error)
      alert('处理失败')
    }
  }

  useEffect(() => {
    checkHealth()
    fetchVideos()
  }, [])

  return (
    <div className="app">
      <header className="app-header">
        <h1>🎬 Video Agent</h1>
        <p className="subtitle">视频代理服务 - React + Python FastAPI</p>
        <div className="health-status">
          后端状态: <span className={health.includes('失败') ? 'error' : 'success'}>{health}</span>
        </div>
      </header>

      <main className="app-main">
        <section className="section">
          <h2>视频列表</h2>
          {loading ? (
            <p>加载中...</p>
          ) : (
            <div className="video-grid">
              {videos.length > 0 ? (
                videos.map((video) => (
                  <div key={video.id} className="video-card">
                    <h3>{video.title}</h3>
                    <p>时长: {video.duration}</p>
                    <button onClick={() => processVideo(video.id)}>
                      处理视频
                    </button>
                  </div>
                ))
              ) : (
                <p>暂无视频</p>
              )}
            </div>
          )}
        </section>

        <section className="section">
          <h2>API 端点</h2>
          <ul className="api-list">
            <li>
              <code>GET /api/health</code> - 健康检查
            </li>
            <li>
              <code>GET /api/videos</code> - 获取视频列表
            </li>
            <li>
              <code>POST /api/videos/process</code> - 处理视频
            </li>
          </ul>
          <a 
            href="/docs" 
            target="_blank" 
            className="docs-link"
          >
            📚 查看完整 API 文档
          </a>
        </section>
      </main>
    </div>
  )
}

export default App
