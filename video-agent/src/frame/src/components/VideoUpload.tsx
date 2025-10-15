import { useState, useRef } from 'react'

interface VideoUploadProps {
  onVideoSelect: (file: File, base64: string) => void
  disabled?: boolean
}

export function VideoUpload({ onVideoSelect, disabled = false }: VideoUploadProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

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

  const handleFileSelect = async (file: File) => {
    if (!file.type.startsWith('video/')) {
      alert('请选择视频文件！')
      return
    }

    if (file.size > 100 * 1024 * 1024) { // 100MB限制
      alert('视频文件大小不能超过100MB！')
      return
    }

    setIsProcessing(true)
    try {
      const base64 = await convertToBase64(file)
      onVideoSelect(file, base64)
    } catch (error) {
      console.error('视频转换失败:', error)
      alert('视频处理失败，请重试！')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    
    if (disabled || isProcessing) return
    
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      handleFileSelect(files[0])
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    if (!disabled && !isProcessing) {
      setIsDragging(true)
    }
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleClick = () => {
    if (!disabled && !isProcessing) {
      fileInputRef.current?.click()
    }
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      handleFileSelect(files[0])
    }
    // 清空input，允许重复选择同一文件
    e.target.value = ''
  }

  return (
    <div className="video-upload-container">
      <div
        className={`video-upload-area ${isDragging ? 'dragging' : ''} ${disabled ? 'disabled' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          onChange={handleFileInputChange}
          style={{ display: 'none' }}
          disabled={disabled}
        />
        
        {isProcessing ? (
          <div className="upload-processing">
            <div className="upload-spinner"></div>
            <p>正在处理视频...</p>
          </div>
        ) : (
          <div className="upload-content">
            <div className="upload-icon">🎥</div>
            <p className="upload-text">
              {isDragging ? '松开鼠标上传视频' : '点击或拖拽上传视频'}
            </p>
            <p className="upload-hint">
              支持 MP4, AVI, MOV 等格式，最大 100MB
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
