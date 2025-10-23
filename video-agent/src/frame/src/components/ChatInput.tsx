import { useRef, useEffect } from 'react'

interface ChatInputProps {
  inputValue: string
  setInputValue: (value: string) => void
  onSend: () => void
  isLoading: boolean
  onVideoSelect?: (file: File, base64: string) => void
  onImageSelect?: (file: File, base64: string) => void
  generatorType?: string
  setGeneratorType?: (type: string) => void
}

export function ChatInput({ inputValue, setInputValue, onSend, isLoading, onVideoSelect, onImageSelect }: ChatInputProps) {
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

  // 统一文件上传处理
  const handleFileUpload = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click()
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      const file = files[0]
      
      // 根据文件类型自动判断处理方式
      if (file.type.startsWith('video/')) {
        // 视频文件处理
        if (!onVideoSelect) {
          alert('当前不支持视频上传！')
          return
        }

        if (file.size > 100 * 1024 * 1024) { // 100MB限制
          alert('视频文件大小不能超过100MB！')
          return
        }

        try {
          const base64 = await convertToBase64(file)
          onVideoSelect(file, base64)
          // 自动填入分析提示
          if (!inputValue.trim()) {
            setInputValue('分析这个视频的内容')
          }
        } catch (error) {
          console.error('视频转换失败:', error)
          alert('视频处理失败，请重试！')
        }
      } else if (file.type.startsWith('image/')) {
        // 图片文件处理
        if (!onImageSelect) {
          alert('当前不支持图片上传！')
          return
        }

        if (file.size > 10 * 1024 * 1024) { // 10MB限制
          alert('图片文件大小不能超过10MB！')
          return
        }

        try {
          const base64 = await convertToBase64(file)
          onImageSelect(file, base64)
          // 自动填入生成提示
          if (!inputValue.trim()) {
            setInputValue('基于这张图片生成一张类似的图片')
          }
        } catch (error) {
          console.error('图片转换失败:', error)
          alert('图片处理失败，请重试！')
        }
      } else {
        alert('请选择图片或视频文件！')
        return
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
      {/* 生成器类型选择器 */}
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
          {(onVideoSelect || onImageSelect) && (
            <button
              className="file-upload-btn"
              onClick={handleFileUpload}
              disabled={isLoading}
              title="上传文件（支持图片和视频）"
            >
              📎
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
      
      {/* 隐藏的文件输入 - 支持图片和视频 */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,video/*"
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />
    </div>
  )
}
