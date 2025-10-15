export interface Message {
  role: 'user' | 'assistant' | 'error'
  content: string
  intent?: string
  timestamp?: number
  metadata?: {
    title?: string
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
  result?: any
  context_info?: any
  error?: string
}
