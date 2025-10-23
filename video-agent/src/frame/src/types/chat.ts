export interface Message {
  role: 'user' | 'assistant' | 'error' | 'system'
  content: string
  contentType?: 'text' | 'video' | 'image' | 'file'  // 重命名为 contentType 避免与 SSE 的 type 冲突
  intent?: string
  timestamp?: number
  metadata?: {
    title?: string
    task_id?: string
    status?: string
    progress?: number
    isFinalReply?: boolean
    isStatusUpdate?: boolean
    [key: string]: unknown
  }
}

export interface Session {
  session_id: string
  title: string
  last_activity: number
  message_count: number
  metadata?: {
    [key: string]: unknown
  }
}

export interface ChatResponse {
  success: boolean
  session_id: string
  intent?: string
  confidence?: number
  message?: string
  result?: unknown
  context_info?: unknown
  error?: string
}
