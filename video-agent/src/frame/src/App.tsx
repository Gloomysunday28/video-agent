import { BrowserRouter, Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import ChatPage from './pages/ChatPage'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/chat" element={<ChatPage />} />
        {/* TODO: 添加 generate 和 analyze 页面 */}
        <Route path="/generate" element={<div style={{padding: '2rem', color: 'white'}}>视频生成页面开发中...</div>} />
        <Route path="/analyze" element={<div style={{padding: '2rem', color: 'white'}}>视频分析页面开发中...</div>} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
