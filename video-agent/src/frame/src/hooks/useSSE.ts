import { useState, useEffect, useCallback, useRef } from 'react'

export interface SSEMessage {
  type: string
  task_id?: string
  status?: string
  progress?: number
  message?: string
  content?: string
  timestamp?: string
  data?: unknown
}

export interface TaskStatus {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  message: string
  progress?: number
  timestamp: string
}

export interface SSEState {
  isConnected: boolean
  connectionId?: string
  messages: SSEMessage[]
}

export const useSSE = (sessionId: string, enabled: boolean = true) => {
  const [state, setState] = useState<SSEState>({
    isConnected: false,
    messages: []
  })

  const eventSourceRef = useRef<EventSource | null>(null)

  const connect = useCallback(() => {
    if (!enabled || !sessionId || eventSourceRef.current?.readyState === EventSource.OPEN) {
      console.log('🔌 SSE连接跳过:', { sessionId, readyState: eventSourceRef.current?.readyState })
      return
    }

    console.log('🔌 建立SSE连接:', sessionId)
    
    try {
      const eventSource = new EventSource(`/api/events/${sessionId}`)
      eventSourceRef.current = eventSource

      eventSource.onopen = () => {
        console.log('✅ SSE连接已建立')
        setState(prev => ({ 
          ...prev, 
          isConnected: true 
        }))
      }

      eventSource.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          console.log('📥 接收到SSE消息:', message)
          
          setState(prev => ({
            ...prev,
            messages: [...prev.messages, message]
          }))
        } catch (error) {
          console.error('❌ 解析SSE消息失败:', error)
        }
      }

      eventSource.onerror = (error) => {
        console.error('❌ SSE连接错误:', error)
        setState(prev => ({ 
          ...prev, 
          isConnected: false 
        }))
      }

      eventSource.addEventListener('connected', (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('🔗 SSE连接确认:', data)
          setState(prev => ({
            ...prev,
            connectionId: data.session_id
          }))
        } catch (error) {
          console.error('❌ 解析连接确认失败:', error)
        }
      })

    } catch (error) {
      console.error('❌ 创建SSE连接失败:', error)
    }
  }, [sessionId])

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      console.log('🔌 断开SSE连接')
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    
    setState({
      isConnected: false,
      messages: []
    })
  }, [])

  // 连接管理
  useEffect(() => {
    if (enabled && sessionId) {
      connect()
    }
    
    return () => {
      disconnect()
    }
  }, [enabled, sessionId, connect, disconnect])

  return {
    ...state,
    connect,
    disconnect
  }
}
