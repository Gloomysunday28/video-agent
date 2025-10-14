import { Link } from 'react-router-dom'
import './HomePage.css'

function HomePage() {
  return (
    <div className="home-page">
      <div className="home-container">
        <header className="home-header">
          <h1 className="home-title">
            <span className="title-icon">🎬</span>
            Video Agent
          </h1>
          <p className="home-subtitle">
            AI驱动的视频助手 - 智能对话、生成视频、分析视频
          </p>
        </header>

        <div className="features-grid">
          <Link to="/chat" className="feature-card featured">
            <div className="card-icon">💬</div>
            <h2>智能对话</h2>
            <p>通过自然语言对话，轻松完成视频生成和分析任务</p>
            <span className="card-badge">推荐</span>
          </Link>

          <Link to="/generate" className="feature-card">
            <div className="card-icon">✨</div>
            <h2>视频生成</h2>
            <p>输入文字描述，AI自动生成精美视频</p>
          </Link>

          <Link to="/analyze" className="feature-card">
            <div className="card-icon">🔍</div>
            <h2>视频分析</h2>
            <p>智能识别视频内容，提取关键信息</p>
          </Link>
        </div>

        <footer className="home-footer">
          <p>Powered by Video Agent • FastAPI + React + AI</p>
        </footer>
      </div>
    </div>
  )
}

export default HomePage

