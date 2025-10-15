import { useRef, useEffect } from 'react'

interface ChatInputProps {
  inputValue: string
  setInputValue: (value: string) => void
  onSend: () => void
  isLoading: boolean
  onVideoSelect?: (file: File, base64: string) => void
}

export function ChatInput({ inputValue, setInputValue, onSend, isLoading, onVideoSelect }: ChatInputProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 自动聚焦输入框
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // 自动调整输入框高度
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 240)}px`
    }
  }, [inputValue])

  // 视频上传处理
  const handleVideoUpload = () => {
    if (fileInputRef.current && onVideoSelect) {
      fileInputRef.current.click()
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0 && onVideoSelect) {
      const file = files[0]
      
      if (!file.type.startsWith('video/')) {
        alert('请选择视频文件！')
        return
      }

      if (file.size > 100 * 1024 * 1024) { // 100MB限制
        alert('视频文件大小不能超过100MB！')
        return
      }

      try {
        const base64 = await convertToBase64(file)
        onVideoSelect(file, base64)
      } catch (error) {
        console.error('视频转换失败:', error)
        alert('视频处理失败，请重试！')
      }
    }
    // 清空input，允许重复选择同一文件
    e.target.value = ''
  }

  const convertToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const result = reader.result as string
        // 移除 data:video/xxx;base64, 前缀
        const base64 = result.split(',')[1]
        resolve(base64)
      }
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value)
  }

  return (
    <div className="input-container">
      <div className="input-wrapper">
        <textarea
          ref={inputRef}
          className="message-input"
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="输入消息... (Shift+Enter 换行，Enter 发送)"
          disabled={isLoading}
          rows={2}
        />
        <div className="input-buttons">
          {onVideoSelect && (
            <button
              className="video-upload-btn"
              onClick={handleVideoUpload}
              disabled={isLoading}
              title="上传视频"
            >
              🎥
            </button>
          )}
          <button
            className="send-button"
            onClick={onSend}
            disabled={!inputValue.trim() || isLoading}
          >
            {isLoading ? '⏳' : '📤'}
          </button>
        </div>
      </div>
      
      {/* 隐藏的文件输入 */}
      <input
        ref={fileInputRef}
        type="file"
        accept="video/*"
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />
    </div>
  )
}
